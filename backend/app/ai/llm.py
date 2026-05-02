"""
Single gateway for all AI clients.
Import LLM, embeddings, and OpenAI SDK client from this module only.
Never instantiate AI clients elsewhere in the codebase.
"""

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from openai import OpenAI

from app.core.config import settings

# LangChain LLM — use in LCEL chains
llm = ChatOpenAI(
    model=settings.LLM_MODEL,
    base_url=settings.LITELLM_PROXY_URL,
    api_key=settings.LITELLM_API_KEY,
    timeout=30,
    max_retries=2,
)

# LangChain embeddings — use for ChromaDB ingestion and retrieval
embeddings = OpenAIEmbeddings(
    model=settings.LITELLM_EMBEDDING_MODEL,
    base_url=settings.LITELLM_PROXY_URL,
    api_key=settings.LITELLM_API_KEY,
)

# OpenAI SDK client — use for direct calls (image generation, etc.)
openai_client = OpenAI(
    api_key=settings.LITELLM_API_KEY,
    base_url=settings.LITELLM_PROXY_URL,
)
