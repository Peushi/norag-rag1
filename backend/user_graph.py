"""Build the concept graph for the user's own documents, incrementally.

Kestrel ships with a committed, manually reviewed graph. "My documents" has
none until the user asks for one: this module plans and runs that build.

- Incremental: only documents that are new or changed (by content hash) are
  sent to the LLM; triples from removed documents are dropped; documents
  with failed chunks are retried on the next build.
- Bounded: at most MAX_CHUNKS_PER_BUILD LLM calls per build, so one click
  cannot spend a whole quota. What is left is reported as still to add.
- One build at a time, in the background, recorded as an indexing trace.
- Only indexed documents are read: documents held for review live outside
  the corpus folder, so they are never sent to the LLM.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import time
from datetime import datetime, timezone

from openai import RateLimitError

from backend import graph_retrieval, rag_service, retrieval
from backend.chunking import chunk_text
from backend.documents import load_documents
from backend.graph_extraction import extract_graph_from_chunk
from backend.llm_config import MISSING_CONFIG_MESSAGE
from backend.retrieval import make_chunk_id
from backend.tracing import create_trace

MAX_CHUNKS_PER_BUILD = 150
RATE_LIMIT_WAIT_SECONDS = 20


class GraphBuildInProgress(RuntimeError):
    """A build for this corpus is already running."""


_lock = threading.Lock()
_builds: dict[str, dict] = {}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _source_prefix(source: str) -> str:
    """Chunk IDs start with a hash of their source (see make_chunk_id)."""
    return make_chunk_id(source, 0).split("::", 1)[0]


def _load_existing(dataset: str) -> dict | None:
    path = graph_retrieval.graph_file(dataset)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def plan_build(dataset: str) -> dict:
    """What a build would do now: which documents are new, changed, or removed."""
    settings = rag_service.APP_SETTINGS
    documents = load_documents(retrieval.DATASET_DIRECTORIES[dataset])
    existing = _load_existing(dataset)
    statistics = (existing or {}).get("statistics", {})
    settings_changed = existing is not None and (
        statistics.get("chunk_size"), statistics.get("overlap")
    ) != (settings.chunk_size, settings.overlap)
    known = {} if settings_changed else (existing or {}).get("documents", {})

    new, changed, unchanged = [], [], []
    chunks_to_extract = 0
    for document in documents:
        previous = known.get(document["source"])
        if previous and previous.get("sha256") == _sha256(document["text"]) and not previous.get("failed_chunks"):
            unchanged.append(document["source"])
            continue
        (changed if previous else new).append(document["source"])
        chunks_to_extract += len(
            chunk_text(document["text"], chunk_size=settings.chunk_size, overlap=settings.overlap)
        )
    current = {document["source"] for document in documents}
    removed = sorted(source for source in known if source not in current)

    return {
        "documents": documents,
        "existing": None if settings_changed else existing,
        "new": new,
        "changed": changed,
        "unchanged": unchanged,
        "removed": removed,
        "chunks_to_extract": chunks_to_extract,
        "settings_changed": settings_changed,
    }


def graph_status(dataset: str) -> dict:
    """Everything the UI needs: built?, up to date?, building?, cost of an update."""
    plan = plan_build(dataset)
    existing = _load_existing(dataset)
    statistics = (existing or {}).get("statistics", {})
    with _lock:
        build = dict(_builds.get(dataset, {}))
    up_to_date = existing is not None and not (
        plan["new"] or plan["changed"] or plan["removed"] or plan["settings_changed"]
    )
    return {
        "dataset": dataset,
        "built": existing is not None,
        "up_to_date": up_to_date,
        "built_at": statistics.get("built_at"),
        "document_count": len(plan["unchanged"]),
        "triple_count": statistics.get("triples", 0),
        "new_documents": plan["new"],
        "changed_documents": plan["changed"],
        "removed_documents": plan["removed"],
        "settings_changed": plan["settings_changed"],
        "llm_calls_needed": plan["chunks_to_extract"],
        "max_llm_calls_per_build": MAX_CHUNKS_PER_BUILD,
        "building": build.get("running", False),
        "progress_done": build.get("done", 0),
        "progress_total": build.get("total", 0),
        "build_trace_id": build.get("trace_id"),
        "last_error": build.get("error"),
    }


def _extract_with_retry(chunk: dict, *, trace, dataset: str) -> dict:
    try:
        return extract_graph_from_chunk(chunk, trace=trace, dataset=dataset)
    except RateLimitError:
        # Free tiers allow only a few requests per minute: wait once, then retry.
        time.sleep(RATE_LIMIT_WAIT_SECONDS)
        return extract_graph_from_chunk(chunk, trace=trace, dataset=dataset)


def _save_atomically(dataset: str, graph: dict) -> None:
    path = graph_retrieval.graph_file(dataset)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            json.dump(graph, file, indent=2, ensure_ascii=False)
        os.replace(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


def build_graph(dataset: str, *, trace, on_progress=lambda done, total: None) -> dict:
    """Run one incremental build synchronously and save the graph."""
    settings = rag_service.APP_SETTINGS
    with trace.span("graph_plan", attributes={"dataset": dataset}) as span:
        plan = plan_build(dataset)
        span.set_attribute("new_count", len(plan["new"]))
        span.set_attribute("changed_count", len(plan["changed"]))
        span.set_attribute("removed_count", len(plan["removed"]))
        span.set_attribute("chunks_to_extract", plan["chunks_to_extract"])

    existing = plan["existing"] or {}
    kept_sources = set(plan["unchanged"])
    kept_prefixes = {_source_prefix(source) for source in kept_sources}
    triples = [
        triple for triple in existing.get("triples", [])
        if str(triple.get("chunk_id", "")).split("::", 1)[0] in kept_prefixes
    ]
    documents = {
        source: info for source, info in existing.get("documents", {}).items()
        if source in kept_sources
    }
    failed_chunks = []
    budget = MAX_CHUNKS_PER_BUILD
    total = min(plan["chunks_to_extract"], MAX_CHUNKS_PER_BUILD)
    done = 0
    remaining = []
    on_progress(done, total)

    by_source = {document["source"]: document for document in plan["documents"]}
    for source in plan["new"] + plan["changed"]:
        document = by_source[source]
        chunks = chunk_text(document["text"], chunk_size=settings.chunk_size, overlap=settings.overlap)
        if len(chunks) > budget:
            remaining.append(source)
            continue
        document_triples, document_failures = [], 0
        for chunk in chunks:
            chunk_data = {
                "id": make_chunk_id(source, chunk["position"]),
                "text": chunk["text"],
                "source": source,
                "position": chunk["position"],
            }
            try:
                result = _extract_with_retry(chunk_data, trace=trace, dataset=dataset)
                document_triples.extend(triple.model_dump() for triple in result["triples"])
            except Exception as exc:  # recorded; the document is retried next build
                document_failures += 1
                failed_chunks.append({
                    "chunk_id": chunk_data["id"],
                    "source": source,
                    "position": chunk["position"],
                    "error": type(exc).__name__,
                })
            budget -= 1
            done += 1
            on_progress(done, total)
        triples.extend(document_triples)
        documents[source] = {
            "sha256": _sha256(document["text"]),
            "chunks": len(chunks),
            "triples": len(document_triples),
            "failed_chunks": document_failures,
        }

    graph = {
        "triples": triples,
        "documents": documents,
        "failed_chunks": failed_chunks,
        "statistics": {
            "documents": len(documents),
            "triples": len(triples),
            "chunk_size": settings.chunk_size,
            "overlap": settings.overlap,
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "llm_calls": done,
            "failed_chunks": len(failed_chunks),
            "documents_left_for_next_build": len(remaining),
        },
    }
    with trace.span("graph_save", attributes={"dataset": dataset}) as span:
        _save_atomically(dataset, graph)
        span.set_attribute("triple_count", len(triples))
        span.set_attribute("document_count", len(documents))
        span.set_attribute("failed_chunk_count", len(failed_chunks))
        span.set_attribute("documents_left_count", len(remaining))
    return graph["statistics"]


def start_build(dataset: str) -> str:
    """Start a background build; returns its trace ID."""
    if dataset not in graph_retrieval.BUILDABLE_DATASETS:
        raise ValueError(f"The {dataset} concept graph cannot be rebuilt from the app.")
    # Fail now, not chunk by chunk, when no LLM is configured.
    from backend import llm_service

    if llm_service.client is None:
        raise llm_service.LLMServiceUnavailable(MISSING_CONFIG_MESSAGE)
    with _lock:
        if _builds.get(dataset, {}).get("running"):
            raise GraphBuildInProgress("A concept map build is already running.")
        trace = create_trace("indexing")
        _builds[dataset] = {"running": True, "done": 0, "total": 0, "trace_id": trace.trace_id, "error": None}

    def progress(done: int, total: int) -> None:
        with _lock:
            _builds[dataset].update(done=done, total=total)

    def run() -> None:
        try:
            statistics = build_graph(dataset, trace=trace, on_progress=progress)
            trace.set_outcome("indexed" if not statistics["failed_chunks"] else "partial")
            trace.finish("completed")
        except Exception as exc:
            # The message is shown in the UI; keep it generic (no paths or text).
            with _lock:
                _builds[dataset]["error"] = (
                    "The LLM is not configured." if type(exc).__name__ == "LLMServiceUnavailable"
                    else "The concept map could not be built. See the trace for details."
                )
            trace.set_outcome("failed")
            trace.finish("failed")
        finally:
            with _lock:
                _builds[dataset]["running"] = False

    threading.Thread(target=run, name=f"graph-build-{dataset}", daemon=True).start()
    return trace.trace_id
