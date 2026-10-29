import hashlib

from .documents import load_documents
from .chunking import chunk_text
from .vector_store import get_collection, reset_collection
from .index_settings import load_settings, save_settings, validate_settings

def make_chunk_id(source, position):
    """generate a deterministic ID for a source and chunk position."""
    source_hash = hashlib.sha1(source.encode("utf-8")).hexdigest()[:12]
    return f"{source_hash}::chunk_{position:04d}"


def rebuild_index(chunk_size=None, overlap=None):
    """read every document and rebuild the vector index."""
    settings = load_settings()

    if chunk_size is None:
        chunk_size = settings["chunk_size"]

    if overlap is None:
        overlap = settings["overlap"]

    validate_settings(chunk_size, overlap)

    documents = load_documents()
    collection = reset_collection()
    total_chunks = 0

    for document in documents:
        source = document["source"]

        chunks = chunk_text(
            document["text"],
            chunk_size=chunk_size,
            overlap=overlap,
        )

        if not chunks:
            continue

        ids = [make_chunk_id(source, chunk["position"]) for chunk in chunks]

        texts = [chunk["text"] for chunk in chunks]

        metadatas = [
            {
                "source": source,
                "position": chunk["position"],
                "start": chunk["start"],
            }
            for chunk in chunks
        ]

        # use batches to avoid oversized Chroma requests.
        batch_size = 100

        for start in range(0, len(chunks), batch_size):
            end = start + batch_size

            collection.add(
                ids=ids[start:end],
                documents=texts[start:end],
                metadatas=metadatas[start:end],
            )

        total_chunks += len(chunks)

    return {
        "documents": len(documents),
        "chunks": total_chunks,
        "chunk_size": chunk_size,
        "overlap": overlap,
    }


def update_index_settings(chunk_size: int, overlap: int):
    """Rebuild using new settings, then save them if the rebuild succeeds."""
    validate_settings(chunk_size, overlap)

    stats = rebuild_index(chunk_size=chunk_size, overlap=overlap)
    save_settings(chunk_size=chunk_size, overlap=overlap)

    return stats


def retrieve_chunks(question, top_k=5, selected_documents=None):
    """retrieve the nearest chunks with IDs and source metadata."""

    if not question or not question.strip():
        raise ValueError("Question cannot be empty")

    if top_k < 1:
        raise ValueError("top_k must be at least 1")

    collection = get_collection()

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

