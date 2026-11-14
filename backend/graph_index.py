
import json
import time
from pathlib import Path

from backend.chunking import chunk_text
from backend.retrieval import make_chunk_id
from backend.graph_extraction import extract_graph_from_chunk
from backend.llm_service import TraceContext
from backend.tracing import indexing_operation


PROJECT_ROOT = Path(__file__).resolve().parent.parent
KESTREL_DOCS = PROJECT_ROOT / "kestrel-kb" / "docs"
GRAPH_DIR = PROJECT_ROOT / "kestrel-kb" / "graph"
GRAPH_FILE = GRAPH_DIR / "graph.json"


@indexing_operation
def build_kestrel_graph(chunk_size=800, overlap=80, *, trace: TraceContext | None = None):
    """Extract graph triples from all Kestrel documents."""

    if not KESTREL_DOCS.exists():
        raise FileNotFoundError(f"Kestrel documents not found: {KESTREL_DOCS}")

    documents = sorted(
        path for path in KESTREL_DOCS.rglob("*")
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}
    )

    all_triples = []
    failed_chunks = []
    total_chunks = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    token_usage_available = True
    successful_calls = 0

    start_time = time.perf_counter()

    for document_path in documents:
        with trace.span("load_documents", attributes={"dataset": "kestrel"}) as span:
            text = document_path.read_text(encoding="utf-8")
            span.set_attribute("document_count", 1)

        source = document_path.relative_to(KESTREL_DOCS).as_posix()
        with trace.span("chunking", attributes={"chunk_size": chunk_size, "overlap": overlap}) as span:
            chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
            span.set_attribute("chunk_count", len(chunks))

        print(f"\nProcessing {source}: {len(chunks)} chunks")

        for chunk in chunks:
            total_chunks += 1

            chunk_id = make_chunk_id(source, chunk["position"])

            chunk_data = {
                "id": chunk_id,
                "text": chunk["text"],
                "source": source,
                "position": chunk["position"],
            }

            try:
                result = extract_graph_from_chunk(chunk_data, trace=trace)

                successful_calls += result["llm_calls"]
                all_triples.extend(
                    triple.model_dump()
                    for triple in result["triples"]
                )

                if result["prompt_tokens"] is None or result["completion_tokens"] is None:
                    token_usage_available = False
                else:
                    total_prompt_tokens += result["prompt_tokens"]
                    total_completion_tokens += result["completion_tokens"]

                print(
                    f"  Chunk {chunk['position'] + 1}/{len(chunks)}: "
                    f"{len(result['triples'])} triples"
                )

            except Exception as exc:
                failed_chunks.append({
                    "chunk_id": chunk_id,
                    "source": source,
                    "position": chunk["position"],
                    "error": str(exc),
                })

                print(f"  Chunk {chunk['position'] + 1}: FAILED - {exc}")

    build_time = time.perf_counter() - start_time

    graph_data = {
        "triples": all_triples,
        "statistics": {
            "documents": len(documents),
            "chunks": total_chunks,
            "successful_calls": successful_calls,
            "failed_chunks": len(failed_chunks),
            "triples": len(all_triples),
            "prompt_tokens": total_prompt_tokens if token_usage_available else None,
            "completion_tokens": total_completion_tokens if token_usage_available else None,
            "total_tokens": (
                total_prompt_tokens + total_completion_tokens
                if token_usage_available else None
            ),
            "build_time_seconds": round(build_time, 2),
            "chunk_size": chunk_size,
            "overlap": overlap,
        },
        "failed_chunks": failed_chunks,
    }

    GRAPH_DIR.mkdir(parents=True, exist_ok=True)

    GRAPH_FILE.write_text(
        json.dumps(graph_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nGraph build completed.")
    print(json.dumps(graph_data["statistics"], indent=2))
    print(f"\nSaved graph to: {GRAPH_FILE}")

    return graph_data


@indexing_operation
def retry_failed_graph_chunks(delay_seconds=5, *, trace: TraceContext | None = None):
    """Retry failed Kestrel chunks without rebuilding or losing the existing graph."""

    if not GRAPH_FILE.exists():
        raise FileNotFoundError(
            "Existing graph.json not found. Build the graph first."
        )

    graph_data = json.loads(GRAPH_FILE.read_text(encoding="utf-8"))

    failed_chunks = graph_data.get("failed_chunks", [])

    if not failed_chunks:
        print("No failed chunks to retry.")
        return graph_data

    # Recreate the original chunks so their IDs remain unchanged.
    chunk_lookup = {}

    documents = sorted(
        path for path in KESTREL_DOCS.rglob("*")
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}
    )

    for document_path in documents:
        with trace.span("load_documents", attributes={"dataset": "kestrel"}) as span:
            text = document_path.read_text(encoding="utf-8")
            span.set_attribute("document_count", 1)
        source = document_path.relative_to(KESTREL_DOCS).as_posix()

        with trace.span("chunking", attributes={"chunk_size": 800, "overlap": 80}) as span:
            chunks = chunk_text(text, chunk_size=800, overlap=80)
            span.set_attribute("chunk_count", len(chunks))

        for chunk in chunks:
            chunk_id = make_chunk_id(source, chunk["position"])

            chunk_lookup[chunk_id] = {
                "id": chunk_id,
                "text": chunk["text"],
                "source": source,
                "position": chunk["position"],
            }

    existing_triples = graph_data.setdefault("triples", [])
    invalid_triples = graph_data.setdefault("invalid_triples", [])

    remaining_failures = []
    statistics = graph_data.setdefault("statistics", {})

    successful_calls = 0
    retry_prompt_tokens = 0
    retry_completion_tokens = 0
    token_usage_available = True

    start_time = time.perf_counter()

    print(f"Retrying {len(failed_chunks)} failed chunks...")

    for index, failed in enumerate(failed_chunks):
        chunk_id = failed["chunk_id"]
        chunk = chunk_lookup.get(chunk_id)

        if chunk is None:
            remaining_failures.append(failed)
            print(f"  {chunk_id}: original chunk not found")
            continue

        # Stay below Gemini's free-tier request limit.
        if index > 0:
            time.sleep(delay_seconds)

        try:
            result = extract_graph_from_chunk(chunk, trace=trace)

            successful_calls += result["llm_calls"]

            existing_triples.extend(
                triple.model_dump()
                for triple in result["triples"]
            )

            for invalid in result["invalid_triples"]:
                invalid_triples.append({
                    **invalid,
                    "chunk_id": chunk_id,
                    "source": chunk["source"],
                    "position": chunk["position"],
                })

            if (
                result["prompt_tokens"] is None
                or result["completion_tokens"] is None
            ):
                token_usage_available = False
            else:
                retry_prompt_tokens += result["prompt_tokens"]
                retry_completion_tokens += result["completion_tokens"]

            print(
                f"  {chunk_id}: "
                f"{len(result['triples'])} valid triples, "
                f"{len(result['invalid_triples'])} invalid triples"
            )

        except Exception as exc:
            remaining_failures.append({
                "chunk_id": chunk_id,
                "source": chunk["source"],
                "position": chunk["position"],
                "error": str(exc),
            })

            print(f"  {chunk_id}: FAILED - {exc}")

    retry_time = time.perf_counter() - start_time

    # Remove duplicate triples while preserving existing data.
    unique_triples = {}
    for triple in existing_triples:
        key = json.dumps(triple, sort_keys=True)
        unique_triples[key] = triple

    graph_data["triples"] = list(unique_triples.values())
    graph_data["failed_chunks"] = remaining_failures

    statistics["successful_calls"] = (
        statistics.get("successful_calls", 0) + successful_calls
    )
    statistics["failed_chunks"] = len(remaining_failures)
    statistics["triples"] = len(graph_data["triples"])
    statistics["retry_time_seconds"] = round(
        statistics.get("retry_time_seconds", 0) + retry_time, 2
    )
    statistics["build_time_seconds"] = round(
        statistics.get("build_time_seconds", 0) + retry_time, 2
    )

    if token_usage_available:
        if (
            statistics.get("prompt_tokens") is not None
            and statistics.get("completion_tokens") is not None
        ):
            statistics["prompt_tokens"] += retry_prompt_tokens
            statistics["completion_tokens"] += retry_completion_tokens
            statistics["total_tokens"] = (
                statistics["prompt_tokens"]
                + statistics["completion_tokens"]
            )
        else:
            statistics["retry_prompt_tokens"] = retry_prompt_tokens
            statistics["retry_completion_tokens"] = retry_completion_tokens
    else:
        statistics["total_tokens"] = None

    GRAPH_FILE.write_text(
        json.dumps(graph_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nRetry completed.")
    print(json.dumps(statistics, indent=2))
    print(f"Invalid triples recorded: {len(invalid_triples)}")
    print(f"Remaining failed chunks: {len(remaining_failures)}")
    print(f"Saved graph to: {GRAPH_FILE}")

    return graph_data
