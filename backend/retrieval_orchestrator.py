from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from backend.rank_fusion import reciprocal_rank_fusion

GRAPH_RETRIEVER = "graph"
KESTREL_DATASET = "kestrel"


@dataclass(frozen=True)
class RetrievalQuery:
    question: str
    dataset: str
    top_k: int
    document_ids: tuple[str, ...] | None = None
    chunk_size: int = 800
    overlap: int = 80


@dataclass(frozen=True)
class RetrieverOutput:
    chunks: Sequence[Mapping[str, Any]]
    graph_paths: Sequence[Mapping[str, Any]] = ()


@dataclass(frozen=True)
class OrchestratedRetrieval:
    chunks: list[dict[str, Any]]
    graph_paths: list[dict[str, Any]]
    retrievers: tuple[str, ...]
    graph_chunks: list[dict[str, Any]] = field(default_factory=list)


Retriever = Callable[[RetrievalQuery], RetrieverOutput]


class RetrieverUnavailableError(ValueError):
    """A selected retrieval method has no registered implementation."""


def orchestrate_retrieval(
    query: RetrievalQuery,
    enabled_retrievers: Sequence[str],
    retrievers: Mapping[str, Retriever],
    *,
    final_top_k: int | None = None,
) -> OrchestratedRetrieval:
    """Run enabled retrievers with a common query and fuse their ranked chunks."""
    _validate_query(query)
    if final_top_k is not None and (
        isinstance(final_top_k, bool)
        or not isinstance(final_top_k, int)
        or final_top_k < 1
    ):
        raise ValueError("final_top_k must be a positive integer or None")

    selected = tuple(enabled_retrievers)
    if not selected:
        raise ValueError("At least one retriever must be enabled")
    if len(set(selected)) != len(selected):
        raise ValueError("Retriever selection cannot contain duplicates")

    unknown = [name for name in selected if name not in retrievers]
    if unknown:
        raise RetrieverUnavailableError(
            f"No implementation registered for: {', '.join(unknown)}"
        )
    if GRAPH_RETRIEVER in selected and query.dataset != KESTREL_DATASET:
        raise ValueError("Graph retrieval is only available for the kestrel dataset")

    ranked_results: dict[str, Sequence[Mapping[str, Any]]] = {}
    graph_paths: list[dict[str, Any]] = []
    graph_chunks: list[dict[str, Any]] = []
    for retriever_name in selected:
        output = retrievers[retriever_name](query)
        if not isinstance(output, RetrieverOutput):
            raise TypeError(
                f"Retriever '{retriever_name}' must return RetrieverOutput"
            )
        ranked_results[retriever_name] = output.chunks
        if retriever_name == GRAPH_RETRIEVER:
            graph_paths = [dict(path) for path in output.graph_paths]
            graph_chunks = [dict(chunk) for chunk in output.chunks]

    chunks = reciprocal_rank_fusion(
        ranked_results,
        top_k=query.top_k if final_top_k is None else final_top_k,
    )
    return OrchestratedRetrieval(
        chunks=chunks,
        graph_paths=graph_paths,
        retrievers=selected,
        graph_chunks=graph_chunks,
    )


def _validate_query(query: RetrievalQuery) -> None:
    if not isinstance(query.question, str) or not query.question.strip():
        raise ValueError("Question cannot be empty")
    if not isinstance(query.dataset, str) or not query.dataset.strip():
        raise ValueError("Dataset must be a non-empty string")
    if isinstance(query.top_k, bool) or not isinstance(query.top_k, int) or query.top_k < 1:
        raise ValueError("top_k must be a positive integer")
    if (
        isinstance(query.chunk_size, bool)
        or not isinstance(query.chunk_size, int)
        or query.chunk_size < 1
    ):
        raise ValueError("chunk_size must be a positive integer")
    if (
        isinstance(query.overlap, bool)
        or not isinstance(query.overlap, int)
        or query.overlap < 0
        or query.overlap >= query.chunk_size
    ):
        raise ValueError("overlap must be non-negative and smaller than chunk_size")
    if query.document_ids is not None and any(
        not isinstance(document_id, str) or not document_id
        for document_id in query.document_ids
    ):
        raise ValueError("document_ids must contain non-empty strings")
