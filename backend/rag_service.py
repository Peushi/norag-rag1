from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.documents import CORPUS_DIR, list_documents as list_document_paths
from backend.index_settings import load_settings
from backend.llm_service import generate_answer
from backend.retrieval import (
    filter_by_relevance,
    get_chunk,
    rebuild_index,
    retrieve_chunks as search_chunks,
    update_index_settings,
)
from backend.schemas import AskResponse, RetrievedChunk, SourceChunk
from backend.vector_store import get_collection

DEFAULT_TOP_K = 3


@dataclass
class Settings:
    chunk_size: int
    overlap: int
    top_k: int = DEFAULT_TOP_K
    relevance_threshold: float | None = None


_index_settings = load_settings()
APP_SETTINGS = Settings(
    chunk_size=_index_settings["chunk_size"],
    overlap=_index_settings["overlap"],
)


def list_documents() -> list[dict[str, str | int]]:
    """List supported corpus files using their relative path as stable ID."""
    documents = []
    for path in list_document_paths():
        source = path.relative_to(CORPUS_DIR).as_posix()
        documents.append(
            {
                "id": source,
                "name": source,
                "size_bytes": path.stat().st_size,
            }
        )
    return documents


def read_text_document(document_id: str) -> str:
    """Read one corpus document by its relative source path."""
    from backend.documents import resolve_document_path

    return resolve_document_path(document_id).read_text(encoding="utf-8")


def index_all_documents(
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> dict[str, int]:
    """Rebuild the corpus index; the retrieval implementation indexes all files."""
    stats = rebuild_index(
        chunk_size=chunk_size if chunk_size is not None else APP_SETTINGS.chunk_size,
        overlap=overlap if overlap is not None else APP_SETTINGS.overlap,
    )
    return stats


def retrieve_chunks(
    question: str,
    document_ids: list[str] | None = None,
    top_k: int | None = None,
) -> list[RetrievedChunk]:
    """Search the Chroma index and apply the configured cosine-distance limit."""
    if get_collection().count() == 0 and list_document_paths():
        index_all_documents()

    chunks = search_chunks(
        question=question,
        top_k=APP_SETTINGS.top_k if top_k is None else top_k,
        selected_documents=document_ids,
    )
    chunks = filter_by_relevance(chunks, APP_SETTINGS.relevance_threshold)
    return [RetrievedChunk.model_validate(chunk) for chunk in chunks]


def ask_question(
    question: str,
    document_ids: list[str] | None = None,
    top_k: int | None = None,
) -> AskResponse:
    """Retrieve supporting chunks and delegate grounded answer generation."""
    chunks = retrieve_chunks(question, document_ids=document_ids, top_k=top_k)
    return generate_answer(
        question,
        [chunk.model_dump() for chunk in chunks],
    )


def get_chunk_by_id(chunk_id: str) -> SourceChunk | None:
    """Look up one indexed chunk for a source preview."""
    if get_collection().count() == 0 and list_document_paths():
        index_all_documents()

    chunk: dict[str, Any] | None = get_chunk(chunk_id)
    return SourceChunk.model_validate(chunk) if chunk is not None else None


def delete_document(document_id: str) -> bool:
    """Delete a corpus file and rebuild the index."""
    from backend.documents import delete_document_and_reindex

    try:
        delete_document_and_reindex(
            document_id,
            chunk_size=APP_SETTINGS.chunk_size,
            overlap=APP_SETTINGS.overlap,
        )
    except FileNotFoundError:
        return False
    return True


def update_settings(
    chunk_size: int,
    overlap: int,
    top_k: int,
    relevance_threshold: float | None,
) -> dict[str, int]:
    """Persist indexing settings and update runtime retrieval preferences."""
    stats = update_index_settings(chunk_size, overlap)
    APP_SETTINGS.chunk_size = chunk_size
    APP_SETTINGS.overlap = overlap
    APP_SETTINGS.top_k = top_k
    APP_SETTINGS.relevance_threshold = relevance_threshold
    return stats
