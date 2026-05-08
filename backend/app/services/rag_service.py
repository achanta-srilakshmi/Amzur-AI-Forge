"""
RAG service — document ingestion and retrieval.

Ingestion flow:
  1. Hash the PDF bytes  → skip if already ingested by this user.
  2. Parse PDF with PyPDF.
  3. Split into overlapping chunks.
  4. Embed with OpenAI Embeddings (via LiteLLM proxy).
  5. Upsert into per-user ChromaDB collection.
  6. Persist Document metadata to PostgreSQL.

Retrieval flow:
  1. Embed the user query.
  2. Query ChromaDB for top-k chunks scoped to thread.
  3. Return assembled context string.
"""
import asyncio
import hashlib
import logging
import uuid
from pathlib import Path
from typing import Optional

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import embeddings
from app.ai.rag.chroma import get_user_collection
from app.core.config import settings
from app.models.document import Document
from app.repositories.document_repository import (
    create_document,
    get_document_by_hash_and_user,
    list_documents_for_thread,
    update_document_chunk_count,
)

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 800
_CHUNK_OVERLAP = 150
_TOP_K = 5


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _chunk_id(document_id: uuid.UUID, chunk_index: int) -> str:
    return f"{document_id}::chunk::{chunk_index}"


def _store_pdf_file(file_bytes: bytes, user_id: uuid.UUID, thread_id: uuid.UUID) -> tuple[Path, str]:
    """Persist uploaded PDF bytes and return (absolute_path, relative_path)."""
    pdf_dir = Path(settings.UPLOAD_DIR) / "pdfs" / str(user_id) / str(thread_id)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    doc_id = uuid.uuid4()
    file_path = pdf_dir / f"{doc_id}.pdf"
    file_path.write_bytes(file_bytes)
    relative_path = str(file_path.relative_to(Path(settings.UPLOAD_DIR)))
    return file_path, relative_path


def _load_and_split(file_path: Path) -> list[str]:
    """Load a PDF and return a list of text chunks."""
    loader = PyPDFLoader(str(file_path))
    pages = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=_CHUNK_SIZE,
        chunk_overlap=_CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    docs = splitter.split_documents(pages)
    return [d.page_content for d in docs if d.page_content.strip()]


async def _embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts in a thread-safe manner."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, embeddings.embed_documents, texts
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def ingest_document(
    db: AsyncSession,
    *,
    file_bytes: bytes,
    filename: str,
    user_id: uuid.UUID,
    thread_id: uuid.UUID,
    user_email: str,
) -> tuple[Document, bool]:
    """Ingest a PDF document into ChromaDB.

    Returns:
        (Document, already_processed) — if the same file was already ingested
        by this user, returns the existing record without re-embedding.
    """
    file_hash = _hash_bytes(file_bytes)

    # Persist file to disk
    file_path, relative_path = _store_pdf_file(file_bytes, user_id, thread_id)

    # Duplicate check — same file content, same user
    existing = await get_document_by_hash_and_user(db, file_hash, user_id)
    if existing:
        # Same thread + same file: return existing row
        if existing.thread_id == thread_id:
            logger.info(
                "Document already ingested in this thread (hash=%s) for user %s",
                file_hash[:8],
                user_email,
            )
            return existing, True

        # Different thread: create a new thread-scoped document row and reuse vectors
        logger.info(
            "Reusing existing embeddings for hash=%s in new thread %s",
            file_hash[:8],
            thread_id,
        )
        doc = await create_document(
            db,
            user_id=user_id,
            thread_id=thread_id,
            filename=filename,
            file_path=relative_path,
            file_hash=file_hash,
            chunk_count=0,
        )

        collection = get_user_collection(str(user_id))
        existing_chunks = collection.get(
            where={"document_id": str(existing.id)},
            include=["documents", "embeddings"],
        )
        existing_docs = existing_chunks.get("documents")
        if existing_docs is None:
            existing_docs = []

        existing_embeddings = existing_chunks.get("embeddings")
        if existing_embeddings is None:
            existing_embeddings = []

        if len(existing_docs) > 0 and len(existing_embeddings) > 0:
            ids = [_chunk_id(doc.id, i) for i in range(len(existing_docs))]
            metadatas = [
                {
                    "document_id": str(doc.id),
                    "thread_id": str(thread_id),
                    "user_id": str(user_id),
                    "filename": filename,
                    "chunk_index": i,
                }
                for i in range(len(existing_docs))
            ]
            collection.upsert(
                ids=ids,
                embeddings=existing_embeddings,
                documents=existing_docs,
                metadatas=metadatas,
            )

            await update_document_chunk_count(db, doc.id, len(existing_docs))
            doc.chunk_count = len(existing_docs)
            return doc, True

        # Fallback if source chunks are unavailable in Chroma (rare): parse + re-embed.
        logger.warning(
            "Could not find existing chunks in Chroma for document %s; re-embedding",
            existing.id,
        )

    # Create DB record early so we have the ID for chunk metadata
    doc = await create_document(
        db,
        user_id=user_id,
        thread_id=thread_id,
        filename=filename,
        file_path=relative_path,
        file_hash=file_hash,
        chunk_count=0,
    )

    # Parse + split
    try:
        chunks = _load_and_split(file_path)
    except Exception as exc:
        logger.error("Failed to parse PDF %s: %s", filename, exc)
        raise ValueError(f"Could not parse PDF '{filename}': {exc}") from exc

    if not chunks:
        raise ValueError(f"PDF '{filename}' contained no extractable text.")

    logger.info(
        "Ingesting '%s': %d chunks for user %s", filename, len(chunks), user_email
    )

    # Embed (sync call offloaded to executor)
    vectors = await _embed_texts(chunks)

    # Upsert into per-user ChromaDB collection
    collection = get_user_collection(str(user_id))
    ids = [_chunk_id(doc.id, i) for i in range(len(chunks))]
    metadatas = [
        {
            "document_id": str(doc.id),
            "thread_id": str(thread_id),
            "user_id": str(user_id),
            "filename": filename,
            "chunk_index": i,
        }
        for i in range(len(chunks))
    ]
    collection.upsert(
        ids=ids,
        embeddings=vectors,
        documents=chunks,
        metadatas=metadatas,
    )

    # Update chunk count in DB
    await update_document_chunk_count(db, doc.id, len(chunks))
    doc.chunk_count = len(chunks)

    logger.info(
        "Document '%s' ingested: %d chunks stored in ChromaDB", filename, len(chunks)
    )
    return doc, False


async def retrieve_context(
    query: str,
    user_id: uuid.UUID,
    thread_id: uuid.UUID,
    user_email: str,
    top_k: int = _TOP_K,
) -> Optional[str]:
    """Retrieve relevant context for a query from this user's documents.

    Scoped to the current thread so users only retrieve from documents they
    uploaded in this conversation.

    Returns:
        A formatted context string to inject into the LLM prompt, or None
        if no relevant chunks are found.
    """
    try:
        collection = get_user_collection(str(user_id))

        # Embed query
        loop = asyncio.get_event_loop()
        query_vector = await loop.run_in_executor(
            None, embeddings.embed_query, query
        )

        # Query ChromaDB scoped to this thread
        total_count = collection.count()
        if total_count == 0:
            logger.info("[RAG] Collection is empty for user %s", user_email)
            return None

        results = collection.query(
            query_embeddings=[query_vector],
            n_results=min(top_k, total_count),
            where={"thread_id": str(thread_id)},
            include=["documents", "metadatas", "distances"],
        )

        docs = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        if not docs:
            return None

        # Filter by relevance — cosine distance < 0.8 (similarity > 0.2)
        # text-embedding-3-large distances are typically 0.1–0.6 for on-topic content
        if distances:
            logger.info(
                "[RAG] Top-%d distances: %s",
                len(distances),
                [round(d, 3) for d in distances],
            )
        relevant = [
            (doc, meta, dist)
            for doc, meta, dist in zip(docs, metadatas, distances)
            if dist < 0.8
        ]

        if not relevant:
            logger.info(
                "[RAG] No sufficiently relevant chunks found (best distance=%.3f, threshold=0.8)",
                distances[0] if distances else 1.0,
            )
            # Fallback: use the top retrieved chunks so the model still has thread context.
            relevant = list(zip(docs[:2], metadatas[:2], distances[:2]))
            if not relevant:
                return None

        # Format context
        parts = []
        for doc, meta, dist in relevant:
            filename = meta.get("filename", "document")
            parts.append(f"[Source: {filename}]\n{doc}")

        context = "\n\n---\n\n".join(parts)
        logger.info(
            "Retrieved %d relevant chunk(s) for thread %s (best similarity=%.3f)",
            len(relevant),
            thread_id,
            1 - relevant[0][2],
        )
        return context

    except Exception as exc:
        logger.error("RAG retrieval failed: %s", exc, exc_info=True)
        return None
