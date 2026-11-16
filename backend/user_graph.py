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
from concurrent.futures import ThreadPoolExecutor
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
# Passages sent to the LLM at the same time. Raise it for a paid or local
# server; lower it (e.g. 1) if a free tier keeps answering 429.
GRAPH_CONCURRENCY = max(1, int(os.getenv("LLM_GRAPH_CONCURRENCY", "4")))


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
        "progress_elapsed_seconds": (
            round(time.time() - build["started"], 1)
            if build.get("running") and build.get("started") else None
        ),
        "last_build_seconds": statistics.get("build_seconds"),
        "last_build_llm_calls": statistics.get("llm_calls"),
        "last_build_rate_limited": bool(statistics.get("rate_limited")),
        "concurrency": GRAPH_CONCURRENCY,
        "build_trace_id": build.get("trace_id"),
        "last_error": build.get("error"),
    }


RATE_LIMIT_ATTEMPTS = 3


class _Throttle:
    """Limits how many passages are being extracted at once.

    Starts at GRAPH_CONCURRENCY. The first rate-limit answer (HTTP 429) pauses
    every worker for RATE_LIMIT_WAIT_SECONDS and drops to one call at a time
    for the rest of the build: on a free tier, parallel calls only add
    failures (measured: 4 at a time took 46 s with 3 failed passages, one at
    a time 13 s with none), while a paid or local server keeps the speed-up.
    """

    def __init__(self, limit: int):
        self.limit = limit
        self.active = 0
        self.resume_at = 0.0
        self.rate_limited = False
        self._condition = threading.Condition()

    def __enter__(self):
        with self._condition:
            while self.active >= self.limit or time.time() < self.resume_at:
                self._condition.wait(timeout=max(0.05, min(1.0, self.resume_at - time.time())))
            self.active += 1
        return self

    def __exit__(self, *exc):
        with self._condition:
            self.active -= 1
            self._condition.notify_all()
        return False

    def slow_down(self):
        with self._condition:
            self.rate_limited = True
            self.limit = 1
            self.resume_at = max(self.resume_at, time.time() + RATE_LIMIT_WAIT_SECONDS)
            self._condition.notify_all()


def _extract_with_retry(chunk: dict, *, trace, dataset: str, throttle: _Throttle | None = None) -> dict:
    throttle = throttle or _Throttle(1)
    for attempt in range(1, RATE_LIMIT_ATTEMPTS + 1):
        try:
            with throttle:
                return extract_graph_from_chunk(chunk, trace=trace, dataset=dataset)
        except RateLimitError:
            throttle.slow_down()
            if attempt == RATE_LIMIT_ATTEMPTS:
                raise


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
    remaining = []
    started = time.perf_counter()
    on_progress(0, total)

    # Plan the work: whole documents only, within the call budget.
    by_source = {document["source"]: document for document in plan["documents"]}
    work = []  # (source, chunk_data)
    chunk_counts = {}
    for source in plan["new"] + plan["changed"]:
        document = by_source[source]
        chunks = chunk_text(document["text"], chunk_size=settings.chunk_size, overlap=settings.overlap)
        if len(chunks) > budget:
            remaining.append(source)
            continue
        budget -= len(chunks)
        chunk_counts[source] = len(chunks)
        work.extend(
            (source, {
                "id": make_chunk_id(source, chunk["position"]),
                "text": chunk["text"],
                "source": source,
                "position": chunk["position"],
            })
            for chunk in chunks
        )

    # Extract several passages at once; results are collected per document.
    progress_lock = threading.Lock()
    done = 0
    results: dict[str, dict] = {}
    throttle = _Throttle(GRAPH_CONCURRENCY)

    def extract(item):
        nonlocal done
        source, chunk_data = item
        try:
            result = _extract_with_retry(chunk_data, trace=trace, dataset=dataset, throttle=throttle)
            outcome = {"triples": [t.model_dump() for t in result["triples"]], "error": None}
        except Exception as exc:  # recorded; the document is retried next build
            outcome = {"triples": [], "error": type(exc).__name__}
        with progress_lock:
            done += 1
            on_progress(done, total)
        return chunk_data["id"], outcome

    with ThreadPoolExecutor(max_workers=GRAPH_CONCURRENCY) as pool:
        for chunk_id, outcome in pool.map(extract, work):
            results[chunk_id] = outcome

    # Assemble in document and passage order, so the saved graph is deterministic.
    for source, count in chunk_counts.items():
        document_triples, document_failures = [], 0
        for position in range(count):
            chunk_id = make_chunk_id(source, position)
            outcome = results[chunk_id]
            if outcome["error"]:
                document_failures += 1
                failed_chunks.append({
                    "chunk_id": chunk_id, "source": source,
                    "position": position, "error": outcome["error"],
                })
            document_triples.extend(outcome["triples"])
        triples.extend(document_triples)
        documents[source] = {
            "sha256": _sha256(by_source[source]["text"]),
            "chunks": count,
            "triples": len(document_triples),
            "failed_chunks": document_failures,
        }
    build_seconds = round(time.perf_counter() - started, 1)

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
            "build_seconds": build_seconds,
            "concurrency": GRAPH_CONCURRENCY,
            "rate_limited": throttle.rate_limited,
            "failed_chunks": len(failed_chunks),
            "documents_left_for_next_build": len(remaining),
        },
    }
    with trace.span("graph_save", attributes={"dataset": dataset}) as span:
        _save_atomically(dataset, graph)
        span.set_attribute("triple_count", len(triples))
        span.set_attribute("document_count", len(documents))
        span.set_attribute("failed_chunk_count", len(failed_chunks))
        span.set_attribute(
            "failed_document_count",
            sum(1 for info in documents.values() if info.get("failed_chunks")),
        )
        span.set_attribute("documents_left_count", len(remaining))
        span.set_attribute("llm_calls", done)
        span.set_attribute("build_seconds", build_seconds)
        span.set_attribute("concurrency", GRAPH_CONCURRENCY)
        span.set_attribute("rate_limited", throttle.rate_limited)
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
        _builds[dataset] = {
            "running": True, "done": 0, "total": 0, "started": time.time(),
            "trace_id": trace.trace_id, "error": None,
        }

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
