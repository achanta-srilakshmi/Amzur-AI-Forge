"""
ChromaDB client singleton — import from here only.
One collection per user keeps documents isolated across users.
"""
import logging
from functools import lru_cache

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_chroma_client() -> chromadb.PersistentClient:
    """Return a cached, persistent ChromaDB client."""
    client = chromadb.PersistentClient(
        path=settings.CHROMA_PERSIST_DIR,
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    logger.info("ChromaDB client initialised at %s", settings.CHROMA_PERSIST_DIR)
    return client


def get_user_collection(user_id: str) -> chromadb.Collection:
    """Return (or create) the per-user ChromaDB collection.

    Collection name: ``user_<user_id>``
    Metadata distance function: cosine (matches OpenAI embeddings best).
    """
    client = get_chroma_client()
    collection_name = f"user_{user_id}"
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )
    return collection
