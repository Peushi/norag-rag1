
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from backend.documents import (
    CORPUS_DIR,
    list_documents as list_document_paths,
)
from backend.index_settings import load_settings
from backend.llm_service import TraceContext, generate_answer
from backend.bm25 import retrieve_bm25
from backend.retrieval import (
    ensure_index_current,
    filter_by_relevance,
    get_chunk,
    rebuild_index,
    retrieve_chunks as search_chunks,
    update_index_settings,
)
from backend.retrieval_orchestrator import (
    OrchestratedRetrieval,
    RetrievalQuery,
    RetrieverOutput,
    orchestrate_retrieval,
)
from backend.schemas import (
    AskResponse,
    PathContext,
    PathSupportingChunk,
    RetrieveResponse,
    EvaluationDataset,
    RetrievedChunk,
    RetrieverName,
    SourceChunk,
)
from backend.vector_store import get_collection
from backend.graph_retrieval import GRAPH_FILE, retrieve_graph

DEFAULT_TOP_K = 3
MIN_FUSION_CANDIDATES = 10


def validate_graph_chunking(chunk_size: int, overlap: int) -> None:
    """Graph provenance uses its build settings; do not fuse another chunking."""
    statistics = json.loads(
        GRAPH_FILE.read_text(encoding="utf-8-sig")
    ).get("statistics", {})
    graph_settings = (
        statistics.get("chunk_size", 800),
        statistics.get("overlap", 80),
    )
    if (chunk_size, overlap) != graph_settings:
        raise ValueError(
            f"Graph uses chunk_size={graph_settings[0]}, overlap={graph_settings[1]}; "
            "use matching settings or rebuild the graph before fusion."
        )


def graph_retriever_output(result: dict) -> RetrieverOutput:
    """Adapt native score to the existing shared typed-score fields."""
    chunks = []
    for original in result["chunks"]:
        chunk = dict(original)
        if "graph_score" in chunk:
            chunk["score"] = chunk.pop("graph_score")
            chunk["score_type"] = "graph_path_score"
        chunks.append(chunk)
    return RetrieverOutput(chunks=chunks, graph_paths=result["paths"])


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
    dataset: EvaluationDataset = "baking",
) -> list[RetrievedChunk]:
    """Search the Chroma index and apply the configured cosine-distance limit."""
    ensure_index_current(dataset, APP_SETTINGS.chunk_size, APP_SETTINGS.overlap)

    chunks = search_chunks(
        question=question,
        top_k=APP_SETTINGS.top_k if top_k is None else top_k,
        selected_documents=document_ids,
        dataset=dataset,
    )
    chunks = filter_by_relevance(chunks, APP_SETTINGS.relevance_threshold)
    return [RetrievedChunk.model_validate(chunk) for chunk in chunks]


def retrieve_selected_chunks(
    question: str,
    *,
    retrievers: list[RetrieverName] | None = None,
    document_ids: list[str] | None = None,
    top_k: int | None = None,
    dataset: EvaluationDataset = "baking",
) -> OrchestratedRetrieval:
    """Dispatch selected retrievers and fuse their ranked chunk results."""
    selected_retrievers = tuple(["dense"] if retrievers is None else retrievers)
    result_limit = APP_SETTINGS.top_k if top_k is None else top_k

    def retrieve_dense(query: RetrievalQuery) -> RetrieverOutput:
        chunks = retrieve_chunks(
            question=query.question,
            document_ids=(
                list(query.document_ids)
                if query.document_ids is not None
                else None
            ),
            top_k=query.top_k,
            dataset=query.dataset,
        )
        return RetrieverOutput(
            chunks=[
                {
                    **chunk.model_dump(exclude={"distance"}),
                    "rank": rank,
                    "retriever": "dense",
                    "score": chunk.distance,
                    "score_type": "cosine_distance",
                }
                for rank, chunk in enumerate(chunks, start=1)
            ]
        )

    def retrieve_graph_results(query: RetrievalQuery) -> RetrieverOutput:
        validate_graph_chunking(query.chunk_size, query.overlap)
        result = retrieve_graph(
            question=query.question,
            top_k=query.top_k,
            selected_documents=(
                list(query.document_ids)
                if query.document_ids is not None
                else None
            ),
        )
        return graph_retriever_output(result)

    query = RetrievalQuery(
        question=question,
        dataset=dataset,
        top_k=(
            max(result_limit, MIN_FUSION_CANDIDATES)
            if len(selected_retrievers) > 1
            else result_limit
        ),
        document_ids=tuple(document_ids) if document_ids is not None else None,
        chunk_size=APP_SETTINGS.chunk_size,
        overlap=APP_SETTINGS.overlap,
    )
    result = orchestrate_retrieval(
        query,
        selected_retrievers,
        {
            "dense": retrieve_dense,
            "bm25": retrieve_bm25,
            "graph": retrieve_graph_results,
        },
        final_top_k=result_limit,
    )
    return result


def ask_question(
    question: str,
    document_ids: list[str] | None = None,
    top_k: int | None = None,
    retrievers: list[RetrieverName] | None = None,
    include_path_context: bool = False,
    dataset: EvaluationDataset = "baking",
    trace: TraceContext | None = None,
) -> AskResponse:
    """Retrieve through selected methods and delegate grounded answer generation."""
    selected_retrievers = ["dense"] if retrievers is None else retrievers
    if include_path_context and "graph" not in selected_retrievers:
        raise ValueError("include_path_context requires graph retrieval")

    if trace is None:
        retrieval = retrieve_selected_chunks(
            question,
            retrievers=selected_retrievers,
            document_ids=document_ids,
            top_k=top_k,
            dataset=dataset,
        )
    else:
        with trace.span(
            "retrieval",
            attributes=_retrieval_request_attributes(
                dataset=dataset,
                retrievers=selected_retrievers,
                document_ids=document_ids,
                top_k=top_k,
                include_path_context=include_path_context,
            ),
        ) as span:
            retrieval = retrieve_selected_chunks(
                question,
                retrievers=selected_retrievers,
                document_ids=document_ids,
                top_k=top_k,
                dataset=dataset,
            )
            _record_retrieval_results(span, retrieval)
    path_context = (
        _build_path_context(retrieval.graph_paths, retrieval.graph_chunks)
        if include_path_context
        else None
    )
    answer = generate_answer(
        question,
        retrieval.chunks,
        path_context=path_context,
        trace=trace,
    )
    return answer.model_copy(
        update={
            "retrieval": RetrieveResponse(
                chunks=retrieval.chunks,
                retrievers=list(retrieval.retrievers),
                graph_paths=retrieval.graph_paths,
                graph_supporting_chunks=retrieval.graph_chunks,
                path_context=path_context,
            )
        }
    )


TRACE_STRING_LIMIT = 200


def _retrieval_request_attributes(
    *,
    dataset: str,
    retrievers: list[RetrieverName],
    document_ids: list[str] | None,
    top_k: int | None,
    include_path_context: bool,
) -> dict[str, str | int | float | bool]:
    """Describe the retrieval settings with safe metadata only.

    Selected documents are recorded as a count, not as file names.
    """
    attributes: dict[str, str | int | float | bool] = {
        "dataset": dataset,
        "retrievers": ",".join(retrievers),
        "top_k": APP_SETTINGS.top_k if top_k is None else top_k,
        "chunk_size": APP_SETTINGS.chunk_size,
        "overlap": APP_SETTINGS.overlap,
        "document_filter": "all" if document_ids is None else "selected",
        "include_path_context": include_path_context,
    }
    if document_ids is not None:
        attributes["selected_document_count"] = len(document_ids)
    if APP_SETTINGS.relevance_threshold is not None:
        attributes["relevance_threshold"] = APP_SETTINGS.relevance_threshold
    return attributes


def _found_by(contributions: list[dict[str, Any]]) -> str:
    """Summarize which retrievers found a chunk, e.g. 'dense#2 (cosine_distance 0.3412)'."""
    parts = []
    for contribution in contributions:
        part = f"{contribution['retriever']}#{contribution['rank']}"
        score = contribution.get("score")
        score_type = contribution.get("score_type")
        if isinstance(score, (int, float)) and score_type:
            part += f" ({score_type} {score:.4f})"
        parts.append(part)
    summary = "; ".join(parts)
    if len(summary) > TRACE_STRING_LIMIT:
        summary = summary[: TRACE_STRING_LIMIT - 1] + "…"
    return summary


def _record_retrieval_results(span: Any, retrieval: OrchestratedRetrieval) -> None:
    """Record ranked chunk IDs and retriever contributions, never chunk text."""
    span.set_attribute("result_count", len(retrieval.chunks))
    if "graph" in retrieval.retrievers:
        span.set_attribute("graph_path_count", len(retrieval.graph_paths))

    for chunk in retrieval.chunks:
        prefix = f"result.{chunk['final_rank']}"
        span.set_attribute(f"{prefix}.chunk_id", str(chunk["id"])[:TRACE_STRING_LIMIT])
        span.set_attribute(f"{prefix}.source", str(chunk["source"])[:TRACE_STRING_LIMIT])
        span.set_attribute(f"{prefix}.position", int(chunk["position"]))
        span.set_attribute(f"{prefix}.score", round(float(chunk["final_score"]), 6))
        span.set_attribute(f"{prefix}.found_by", _found_by(chunk["retrievers"]))


def _build_path_context(
    graph_paths: list[dict[str, Any]],
    graph_chunks: list[dict[str, Any]],
) -> PathContext | None:
    if not graph_paths:
        return None

    chunks_by_id: dict[str, dict[str, Any]] = {}
    for chunk in graph_chunks:
        chunk_id = chunk.get("id")
        if not isinstance(chunk_id, str) or not chunk_id:
            raise ValueError("Graph result chunks must have a valid id")
        chunks_by_id[chunk_id] = chunk

    supporting_ids: list[str] = []
    seen_ids: set[str] = set()

    for path in graph_paths:
        chunk_ids = path.get("supporting_chunk_ids")
        if not isinstance(chunk_ids, list) or not chunk_ids:
            raise ValueError("Every graph path must list supporting_chunk_ids")
        for chunk_id in chunk_ids:
            if not isinstance(chunk_id, str) or not chunk_id:
                raise ValueError(
                    "Graph path supporting chunk IDs must be non-empty strings"
                )
            if chunk_id not in chunks_by_id:
                raise ValueError(
                    f"Graph path references unavailable supporting chunk '{chunk_id}'"
                )
            if chunk_id not in seen_ids:
                seen_ids.add(chunk_id)
                supporting_ids.append(chunk_id)

    return PathContext(
        paths=graph_paths,
        supporting_chunks=[
            PathSupportingChunk(
                chunk_id=chunk_id,
                source=chunks_by_id[chunk_id]["source"],
                position=chunks_by_id[chunk_id]["position"],
                text=chunks_by_id[chunk_id]["text"],
            )
            for chunk_id in supporting_ids
        ],
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
