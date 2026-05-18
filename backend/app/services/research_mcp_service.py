"""Research digest agent service backed by the arXiv MCP server."""

# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false

from __future__ import annotations

import json
import logging
import re
from typing import Any, AsyncGenerator, Sequence, TypedDict, cast

from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph  # type: ignore[reportMissingTypeStubs]

from app.ai.llm import llm
from app.core.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)


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
        parsed = json.loads(raw, strict=False)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0), strict=False)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _coerce_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(_coerce_str(item) for item in value if _coerce_str(item).strip())
    if isinstance(value, dict):
        for key in ("text", "name", "title", "href", "id"):
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
    return str(value).strip()


def _normalize_paper(item: dict[str, Any]) -> dict[str, str]:
    title = _coerce_str(item.get("title") or item.get("paper_title") or item.get("name"))
    authors = _coerce_str(item.get("authors") or item.get("author") or item.get("creator"))
    summary = _coerce_str(item.get("summary") or item.get("abstract") or item.get("description"))
    published = _coerce_str(item.get("published") or item.get("published_at") or item.get("date"))
    url = _coerce_str(
        item.get("url")
        or item.get("entry_id")
        or item.get("pdf_url")
        or item.get("link")
        or item.get("id")
    )

    return {
        "title": title,
        "authors": authors or "Unknown",
        "summary": summary,
        "published": published,
        "url": url,
    }


def _extract_papers_from_payload(payload: Any) -> list[dict[str, str]]:
    if isinstance(payload, list):
        papers: list[dict[str, str]] = []
        for item in payload:
            if isinstance(item, dict):
                text_value = item.get("text")
                if isinstance(text_value, str):
                    nested_papers = _extract_papers_from_payload(text_value)
                    if nested_papers:
                        papers.extend(nested_papers)
                        continue

                normalized = _normalize_paper(item)
                if normalized["title"]:
                    papers.append(normalized)
        return papers

    if isinstance(payload, dict):
        for key in ("papers", "results", "items", "entries", "data"):
            nested = payload.get(key)
            nested_papers = _extract_papers_from_payload(nested)
            if nested_papers:
                return nested_papers

        normalized = _normalize_paper(payload)
        return [normalized] if normalized["title"] else []

    if isinstance(payload, str):
        try:
            parsed = json.loads(payload, strict=False)
        except json.JSONDecodeError:
            return []
        return _extract_papers_from_payload(parsed)

    return []


def _tool_name(tool: BaseTool) -> str:
    return str(getattr(tool, "name", "")).strip().lower()


def _tool_description(tool: BaseTool) -> str:
    return str(getattr(tool, "description", "")).strip().lower()


def _pick_search_tool(tools: Sequence[BaseTool]) -> BaseTool:
    scored: list[tuple[int, BaseTool]] = []
    for tool in tools:
        name = _tool_name(tool)
        description = _tool_description(tool)
        haystack = f"{name} {description}"
        score = 0
        if "search" in haystack:
            score += 4
        if "arxiv" in haystack:
            score += 3
        if "paper" in haystack or "article" in haystack:
            score += 1
        if "query" in haystack:
            score += 1
        scored.append((score, tool))

    scored.sort(key=lambda item: item[0], reverse=True)
    if not scored or scored[0][0] <= 0:
        raise RuntimeError("No suitable arXiv MCP search tool was found.")
    return scored[0][1]


async def _invoke_search_tool(tool: BaseTool, query: str) -> list[dict[str, str]]:
    schema_args = getattr(tool, "args", None)
    canonical_args: dict[str, Any] = {}
    if isinstance(schema_args, dict):
        if "query" in schema_args:
            canonical_args["query"] = query
        if "q" in schema_args:
            canonical_args["q"] = query
        if "search_query" in schema_args:
            canonical_args["search_query"] = query
        if "topic" in schema_args:
            canonical_args["topic"] = query
        if "limit" in schema_args:
            canonical_args["limit"] = 3
        if "response_format" in schema_args:
            canonical_args["response_format"] = "json"
        if "sort_by" in schema_args:
            canonical_args["sort_by"] = "relevance"
        if "sort_order" in schema_args:
            canonical_args["sort_order"] = "descending"

    arg_options: list[Any] = []
    if canonical_args:
        arg_options.append(canonical_args)

    arg_options.extend(
        [
            {"query": query},
            {"q": query},
            {"search_query": query},
            {"topic": query},
        ]
    )

    last_error: Exception | None = None
    for candidate in arg_options:
        try:
            result = await tool.ainvoke(candidate)
            papers = _extract_papers_from_payload(result)
            if papers:
                return papers[:5]

            as_text = _extract_message_text(result)
            papers = _extract_papers_from_payload(as_text)
            if papers:
                return papers[:5]

            # The tool call succeeded but returned an unsupported payload shape.
            # Treat as empty results rather than trying incompatible arg schemas.
            return []
        except Exception as exc:  # pragma: no cover - depends on remote tool shape
            last_error = exc

    if last_error is not None:
        raise RuntimeError(f"Failed invoking MCP arXiv search tool: {last_error}") from last_error
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


def _mcp_fallback_digest(reason: str) -> str:
    return (
        "## Overview of the research area\n"
        "Unable to fetch data from the hosted arXiv MCP service right now.\n\n"
        "## Key Papers\n"
        "No papers could be retrieved in this attempt.\n\n"
        "## Common Themes across papers\n"
        "Insufficient source papers were available to extract reliable themes.\n\n"
        "## Further Reading\n"
        f"- MCP connection issue: {reason}\n"
        "- Retry shortly, or switch to Standard mode if MCP endpoint is unreachable."
    )


def _build_graph(user_email: str, mcp_search_tool: BaseTool):
    async def search_node(state: ResearchState) -> dict[str, Any]:
        query = state.get("query") or state.get("topic") or ""
        papers = await _invoke_search_tool(mcp_search_tool, query)
        return {"papers": papers}

    async def evaluate_node(state: ResearchState) -> dict[str, Any]:
        topic = state.get("topic", "")
        query = state.get("query", topic)
        papers = state.get("papers", [])
        retries = int(state.get("retries", 0))

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


async def _load_mcp_search_tool() -> BaseTool:
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "MCP dependencies are not installed. Install backend requirements to use mode=mcp."
        ) from exc

    transport = settings.RESEARCH_MCP_TRANSPORT.strip().lower()
    connection: dict[str, Any]

    if transport == "stdio":
        command = (settings.RESEARCH_MCP_COMMAND or "").strip()
        if not command:
            raise RuntimeError(
                "RESEARCH_MCP_COMMAND must be set when RESEARCH_MCP_TRANSPORT=stdio."
            )
        connection = {
            "transport": "stdio",
            "command": command,
            "args": list(settings.RESEARCH_MCP_ARGS),
        }
    elif transport == "sse":
        mcp_url = (settings.RESEARCH_MCP_URL or "").strip()
        if not mcp_url:
            raise RuntimeError(
                "RESEARCH_MCP_URL must be set when RESEARCH_MCP_TRANSPORT=sse."
            )
        connection = {
            "transport": "sse",
            "url": mcp_url,
        }
    else:
        raise RuntimeError(
            "Unsupported RESEARCH_MCP_TRANSPORT. Use 'sse' or 'stdio'."
        )

    client = MultiServerMCPClient(cast(Any, {"arxiv": connection}))

    tools = await client.get_tools()
    typed_tools = tools
    if not typed_tools:
        raise RuntimeError("No tools were loaded from the arXiv MCP server.")

    llm.bind_tools(typed_tools)
    return _pick_search_tool(typed_tools)


async def run_mcp_research_agent(topic: str, current_user: User) -> AsyncGenerator[str, None]:
    normalized_topic = topic.strip()

    try:
        search_tool = await _load_mcp_search_tool()
    except Exception as exc:
        logger.exception("Failed to initialize MCP arXiv tool: %s", exc)
        fallback = _mcp_fallback_digest("MCP endpoint could not be reached")
        for chunk in _chunk_text(fallback):
            yield _sse("chunk", chunk)
        yield _sse("done", "")
        return

    graph = _build_graph(current_user.email, search_tool)

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
        logger.exception("MCP research stream failed for topic '%s': %s", normalized_topic, exc)
        fallback = _mcp_fallback_digest("MCP request failed during streaming")
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