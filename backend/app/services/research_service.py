"""Research digest agent service built with LangGraph."""

# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date, datetime
from typing import Any, AsyncGenerator, TypedDict

import arxiv
from langgraph.graph import END, START, StateGraph  # type: ignore[reportMissingTypeStubs]

from app.ai.llm import llm
from app.models.user import User

logger = logging.getLogger(__name__)
ARXIV_SEARCH_TIMEOUT_SECONDS = 20

class ResearchState(TypedDict, total=False):
    topic: str
    query: str
    papers: list[dict[str, str]]
    retries: int
    sufficient: bool
    digest: str


def _extract_message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
                continue
            text = getattr(item, "text", None)
            if isinstance(text, str):
                parts.append(text)
        return "\n".join(parts)
    return str(content)


def _extract_json_object(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _format_authors(authors: list[Any]) -> str:
    names = [str(getattr(author, "name", "")).strip() for author in authors]
    authors = [author for author in names if author]
    authors = [author for author in authors if author]
    if not authors:
        return "Unknown"
    if len(authors) <= 4:
        return ", ".join(authors)
    return ", ".join(authors[:4]) + " et al."


async def _search_arxiv(query: str) -> list[dict[str, str]]:
    def _run_search() -> list[dict[str, str]]:
        search = arxiv.Search(
            query=query,
            max_results=5,
            sort_by=arxiv.SortCriterion.Relevance,
            sort_order=arxiv.SortOrder.Descending,
        )
        client = arxiv.Client(page_size=5, delay_seconds=0.0, num_retries=1)

        papers: list[dict[str, str]] = []
        for result in client.results(search):
            published_value = getattr(result, "published", None)
            if isinstance(published_value, datetime):
                published = published_value.date().isoformat()
            elif isinstance(published_value, date):
                published = published_value.isoformat()
            else:
                published = ""

            url = str(getattr(result, "entry_id", "") or getattr(result, "pdf_url", "")).strip()
            title = str(getattr(result, "title", "")).replace("\n", " ").strip()
            summary = str(getattr(result, "summary", "")).replace("\n", " ").strip()
            authors = _format_authors(list(getattr(result, "authors", [])))

            papers.append(
                {
                    "title": title,
                    "authors": authors,
                    "summary": summary,
                    "published": published,
                    "url": url,
                }
            )

        return papers

    try:
        papers = await asyncio.wait_for(
            asyncio.to_thread(_run_search),
            timeout=ARXIV_SEARCH_TIMEOUT_SECONDS,
        )
        return papers[:5]
    except asyncio.TimeoutError:
        logger.warning("arXiv search timed out for query '%s'", query)
        return []
    except arxiv.HTTPError as exc:
        logger.warning("arXiv search failed for query '%s': %s", query, exc)
        return []
    except Exception as exc:
        logger.exception("Unexpected arXiv search error for query '%s': %s", query, exc)
        return []


async def _evaluate_results(
    topic: str,
    query: str,
    papers: list[dict[str, str]],
    retries: int,
    user_email: str,
) -> dict[str, Any]:
    if retries >= 2:
        return {
            "sufficient": True,
            "refined_query": query,
            "reason": "Max retries reached",
        }

    prompt = (
        "You are evaluating whether arXiv search results are sufficient to write a research digest. "
        "Return ONLY valid JSON with keys: sufficient (boolean), refined_query (string), reason (string).\n\n"
        f"Topic: {topic}\n"
        f"Current query: {query}\n"
        f"Retry count: {retries}\n"
        f"Papers found: {len(papers)}\n"
        "Paper titles:\n"
        + "\n".join(f"- {paper['title']}" for paper in papers)
        + "\n\nRules:\n"
        "- If papers are relevant and diverse enough, set sufficient=true.\n"
        "- If insufficient, set sufficient=false and provide a refined_query.\n"
        "- Keep refined_query concise and specific."
    )

    response = await llm.ainvoke(
        prompt,
        config={"metadata": {"user_email": user_email}},
    )
    raw = _extract_message_text(getattr(response, "content", response))
    parsed = _extract_json_object(raw)

    sufficient = bool(parsed.get("sufficient", len(papers) >= 3))
    refined_query = str(parsed.get("refined_query") or query).strip() or query
    reason = str(parsed.get("reason") or "")

    return {
        "sufficient": sufficient,
        "refined_query": refined_query,
        "reason": reason,
    }


def _digest_prompt(topic: str, papers: list[dict[str, str]]) -> str:
    serialized = json.dumps(papers, ensure_ascii=True)
    return (
        "You are a research analyst. Create a structured markdown research digest from the papers below.\n\n"
        f"Topic: {topic}\n"
        f"Papers JSON: {serialized}\n\n"
        "Required sections and exact order:\n"
        "## Overview of the research area\n"
        "## Key Papers\n"
        "- One paragraph per paper including title, authors, date, and main contribution.\n"
        "## Common Themes across papers\n"
        "## Further Reading\n"
        "- Bullet list of arXiv links only.\n\n"
        "Use only evidence from the provided papers and keep the digest factual and concise."
    )


def _chunk_text(text: str, chunk_size: int = 160) -> list[str]:
    if not text:
        return []
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def _sse(event: str, data: str) -> str:
    lines = data.splitlines() or [""]
    payload = "".join(f"data: {line}\n" for line in lines)
    return f"event: {event}\n{payload}\n"


def _build_graph(user_email: str):
    async def search_node(state: ResearchState) -> dict[str, Any]:
        query = state.get("query") or state.get("topic") or ""
        papers = await _search_arxiv(query)
        return {"papers": papers}

    async def evaluate_node(state: ResearchState) -> dict[str, Any]:
        topic = state.get("topic", "")
        query = state.get("query", topic)
        papers = state.get("papers", [])
        retries = int(state.get("retries", 0))

        # If search returned no papers (commonly due to rate limiting),
        # avoid repeated search loops and proceed to a graceful digest.
        if not papers:
            return {
                "sufficient": True,
                "query": query,
                "retries": retries,
            }

        evaluation = await _evaluate_results(topic, query, papers, retries, user_email)
        sufficient = bool(evaluation.get("sufficient", False))

        if sufficient:
            return {
                "sufficient": True,
                "query": query,
                "retries": retries,
            }

        refined_query = str(evaluation.get("refined_query") or query).strip() or query
        return {
            "sufficient": False,
            "query": refined_query,
            "retries": retries + 1,
        }

    async def digest_node(state: ResearchState) -> dict[str, Any]:
        topic = state.get("topic", "")
        papers = state.get("papers", [])
        prompt = _digest_prompt(topic, papers)
        response = await llm.ainvoke(
            prompt,
            config={"metadata": {"user_email": user_email}},
        )
        digest_text = _extract_message_text(getattr(response, "content", response)).strip()
        return {"digest": digest_text}

    def route_after_evaluate(state: ResearchState) -> str:
        retries = int(state.get("retries", 0))
        sufficient = bool(state.get("sufficient", False))
        if not sufficient and retries <= 2:
            return "search"
        return "digest"

    builder = StateGraph(ResearchState)
    builder.add_node("search", search_node)
    builder.add_node("evaluate", evaluate_node)
    builder.add_node("digest", digest_node)

    builder.add_edge(START, "search")
    builder.add_edge("search", "evaluate")
    builder.add_conditional_edges(
        "evaluate",
        route_after_evaluate,
        {
            "search": "search",
            "digest": "digest",
        },
    )
    builder.add_edge("digest", END)

    return builder.compile()


async def run_research_agent(topic: str, current_user: User) -> AsyncGenerator[str, None]:
    normalized_topic = topic.strip()
    graph = _build_graph(current_user.email)

    state: ResearchState = {
        "topic": normalized_topic,
        "query": normalized_topic,
        "papers": [],
        "retries": 0,
        "sufficient": False,
        "digest": "",
    }

    yield _sse("step", "search")

    try:
        async for update in graph.astream(state):
            for node_name, node_state in update.items():
                if isinstance(node_state, dict):
                    state.update(node_state)

                if node_name == "search":
                    yield _sse("step", "evaluate")
                elif node_name == "evaluate":
                    retries = int(state.get("retries", 0))
                    sufficient = bool(state.get("sufficient", False))
                    if not sufficient and retries <= 2:
                        yield _sse("step", "search")
                    else:
                        yield _sse("step", "digest")
    except Exception as exc:
        logger.exception("Research agent stream failed for topic '%s': %s", normalized_topic, exc)
        fallback = (
            "## Overview of the research area\n"
            "Unable to fetch arXiv results right now due to temporary upstream limits.\n\n"
            "## Key Papers\n"
            "No papers could be retrieved in this attempt.\n\n"
            "## Common Themes across papers\n"
            "Insufficient source papers were available to extract reliable themes.\n\n"
            "## Further Reading\n"
            "- Retry in a minute, or switch to MCP mode for alternate tool access."
        )
        for chunk in _chunk_text(fallback):
            yield _sse("chunk", chunk)
        yield _sse("done", "")
        return

    digest = str(state.get("digest", ""))
    for chunk in _chunk_text(digest):
        yield _sse("chunk", chunk)

    papers = state.get("papers", [])
    if papers:
        yield _sse("papers", json.dumps(papers, ensure_ascii=True))

    yield _sse("done", "")
