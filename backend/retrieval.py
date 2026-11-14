from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING

from .documents import PROJECT_ROOT, load_documents
from .chunking import chunk_text
from .vector_store import get_collection, reset_collection
from .index_settings import load_settings, save_settings, validate_settings
from .schemas import EvaluationDataset
from .tracing import indexing_operation
if TYPE_CHECKING:
    from .llm_service import TraceContext

DATASET_DIRECTORIES: dict[EvaluationDataset, Path] = {
    "baking": PROJECT_ROOT / "corpus",
    "kestrel": PROJECT_ROOT / "kestrel-kb" / "docs",
}


def make_chunk_id(source, position):
    """generate a deterministic ID for a source and chunk position."""
    source_hash = hashlib.sha1(source.encode("utf-8")).hexdigest()[:12]
    return f"{source_hash}::chunk_{position:04d}"


def _index_metadata(documents, chunk_size, overlap):
    """Fingerprint source content and settings so Dense/BM25 cannot mix indexes."""
    content = json.dumps(documents, ensure_ascii=False, sort_keys=True)
    return {
        "corpus_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "chunk_size": chunk_size,
        "overlap": overlap,
    }


def ensure_index_current(dataset, chunk_size, overlap, *, trace: TraceContext | None = None):
    """Rebuild legacy/stale Dense indexes before retrieval or fusion."""
    validate_settings(chunk_size, overlap)
    if dataset not in DATASET_DIRECTORIES:
        raise ValueError(f"Unknown retrieval dataset: {dataset}")
    documents = load_documents(DATASET_DIRECTORIES[dataset])
    expected = _index_metadata(documents, chunk_size, overlap)
    collection = get_collection(dataset)
    if any((collection.metadata or {}).get(key) != value for key, value in expected.items()):
        rebuild_index(chunk_size, overlap, dataset, trace=trace)


@indexing_operation
def rebuild_index(
    chunk_size=None,
    overlap=None,
    dataset: EvaluationDataset = "baking",
    *,
    documents=None,
    trace: TraceContext | None = None,
):
    """Rebuild using one shared trace; implicit Chroma embedding stays unchanged."""
    if dataset not in DATASET_DIRECTORIES:
        raise ValueError("Unknown retrieval dataset")
    settings = load_settings()
    chunk_size = settings["chunk_size"] if chunk_size is None else chunk_size
    overlap = settings["overlap"] if overlap is None else overlap
    validate_settings(chunk_size, overlap)

    with trace.span("load_documents", attributes={"dataset": dataset}) as span:
        preloaded = documents is not None
        if documents is None:
            documents = load_documents(DATASET_DIRECTORIES[dataset])
        span.set_attribute("document_count", len(documents))
        span.set_attribute("preloaded", preloaded)

    with trace.span("chunking", attributes={"chunk_size": chunk_size, "overlap": overlap}) as span:
        prepared = [
            (
                document["source"],
                chunk_text(document["text"], chunk_size=chunk_size, overlap=overlap),
            )
            for document in documents
        ]
        total_chunks = sum(len(chunks) for _, chunks in prepared)
        span.set_attribute("chunk_count", total_chunks)

    with trace.span("embedding_indexing", attributes={
        "model": "all-MiniLM-L6-v2", "vector_count": 0,
    }) as span:
        collection = reset_collection(dataset)
        indexed = 0
        for source, chunks in prepared:
            for start in range(0, len(chunks), 100):
                batch = chunks[start:start + 100]
                collection.add(
                    ids=[make_chunk_id(source, chunk["position"]) for chunk in batch],
                    documents=[chunk["text"] for chunk in batch],
                    metadatas=[
                        {"source": source, "position": chunk["position"], "start": chunk["start"]}
                        for chunk in batch
                    ],
                )
                indexed += len(batch)
                span.set_attribute("vector_count", indexed)
        collection.modify(metadata=_index_metadata(documents, chunk_size, overlap))
    return {
        "documents": len(documents),
        "chunks": total_chunks,
        "chunk_size": chunk_size,
        "overlap": overlap,
        "dataset": dataset,
    }


@indexing_operation
def update_index_settings(chunk_size: int, overlap: int, *, trace: TraceContext | None = None):
    """Rebuild and save settings under the same operation trace."""
    validate_settings(chunk_size, overlap)
    stats = rebuild_index(chunk_size=chunk_size, overlap=overlap, trace=trace)
    save_settings(chunk_size=chunk_size, overlap=overlap)
    return stats


def retrieve_chunks(
    question,
    top_k=5,
    selected_documents=None,
    dataset: EvaluationDataset = "baking",
):
    """retrieve the nearest chunks with IDs and source metadata."""

    if not question or not question.strip():
        raise ValueError("Question cannot be empty")

    if top_k < 1:
        raise ValueError("top_k must be at least 1")

    if dataset not in DATASET_DIRECTORIES:
        raise ValueError(f"Unknown retrieval dataset: {dataset}")

    collection = get_collection(dataset)

    if collection.count() == 0:
        return []

    where_filter = None

    if selected_documents is not None:
        if not selected_documents:
            return []

        where_filter = {"source": {"$in": selected_documents}}

    results = collection.query(
        query_texts=[question],
        n_results=top_k,
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    chunks = []

    for i, chunk_id in enumerate(results["ids"][0]):
        metadata = results["metadatas"][0][i]

        chunks.append(
            {
                "id": chunk_id,
                "text": results["documents"][0][i],
                "source": metadata["source"],
                "position": metadata["position"],
                "distance": float(results["distances"][0][i]),
            }
        )

    return chunks


def get_chunk(chunk_id):
    """Fetch one stored chunk by its deterministic ID."""
    collection = get_collection()
    if collection.count() == 0:
        return None

    result = collection.get(ids=[chunk_id], include=["documents", "metadatas"])
    if not result.get("ids") or not result["ids"]:
        return None

    document = result["documents"][0]
    metadata = result["metadatas"][0]

    return {
        "id": chunk_id,
        "text": document,
        "source": metadata["source"],
        "position": metadata["position"],
    }


def filter_by_relevance(chunks, max_distance=None):
    """optionally remove chunks that are too far from the query."""

    if max_distance is None:
        return chunks

    if not 0 <= max_distance <= 2:
        raise ValueError("Cosine distance threshold must be between 0 and 2")

    return [chunk for chunk in chunks if chunk["distance"] <= max_distance]


def get_chunk(chunk_id: str):
    """Return one indexed chunk by its ID, or None if it doesn't exist."""
    collection = get_collection()

    if collection.count() == 0:
        return None

    results = collection.get(
        ids=[chunk_id],
        include=["documents", "metadatas"],
    )

    if not results["ids"]:
        return None

    metadata = results["metadatas"][0]

    return {
        "id": results["ids"][0],
        "text": results["documents"][0],
        "source": metadata["source"],
        "position": metadata["position"],
        "distance": 0.0,
    }
