from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

RRF_CONSTANT = 60


def reciprocal_rank_fusion(
    ranked_results: Mapping[str, Sequence[Mapping[str, Any]]],
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """Fuse ranked chunk lists using rank-only Reciprocal Rank Fusion."""
    if top_k is not None and (
        isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1
    ):
        raise ValueError("top_k must be a positive integer or None")

    chunks_by_id: dict[str, dict[str, Any]] = {}
    contributions_by_id: dict[str, list[dict[str, Any]]] = {}
    score_terms_by_id: dict[str, list[float]] = {}

    for retriever, chunks in ranked_results.items():
        if not isinstance(retriever, str) or not retriever.strip():
            raise ValueError("Retriever names must be non-empty strings")

        seen_ids: set[str] = set()
        seen_ranks: set[int] = set()
        for chunk in chunks:
            chunk_id = chunk.get("id")
            rank = chunk.get("rank")
            if not isinstance(chunk_id, str) or not chunk_id:
                raise ValueError(f"{retriever} returned a chunk without a valid id")
            if isinstance(rank, bool) or not isinstance(rank, int) or rank < 1:
                raise ValueError(
                    f"{retriever} chunk '{chunk_id}' must have a positive integer rank"
                )
            if chunk_id in seen_ids:
                raise ValueError(
                    f"{retriever} returned chunk '{chunk_id}' more than once"
                )
            if rank in seen_ranks:
                raise ValueError(f"{retriever} returned duplicate rank {rank}")
            seen_ids.add(chunk_id)
            seen_ranks.add(rank)

            chunk_retriever = chunk.get("retriever")
            if chunk_retriever != retriever:
                raise ValueError(
                    f"Chunk '{chunk_id}' retriever must match list name '{retriever}'"
                )

            text = chunk.get("text")
            source = chunk.get("source")
            position = chunk.get("position")
            if not isinstance(text, str):
                raise ValueError(f"Chunk '{chunk_id}' must have text")
            if not isinstance(source, str) or not source:
                raise ValueError(f"Chunk '{chunk_id}' must have a valid source")
            if (
                isinstance(position, bool)
                or not isinstance(position, int)
                or position < 0
            ):
                raise ValueError(f"Chunk '{chunk_id}' must have a valid position")

            has_score = "score" in chunk
            has_score_type = "score_type" in chunk
            if has_score != has_score_type:
                raise ValueError(
                    f"Chunk '{chunk_id}' must provide both score and score_type"
                )
            score = chunk.get("score")
            score_type = chunk.get("score_type")
            if has_score and (
                isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not math.isfinite(score)
                or not isinstance(score_type, str)
                or not score_type.strip()
            ):
                raise ValueError(f"Chunk '{chunk_id}' has an invalid typed score")

            chunk_data = {
                "id": chunk_id,
                "text": text,
                "source": source,
                "position": position,
            }
            existing = chunks_by_id.get(chunk_id)
            if existing is not None and existing != chunk_data:
                raise ValueError(
                    f"Chunk '{chunk_id}' has conflicting content or metadata"
                )
            chunks_by_id[chunk_id] = chunk_data

            contribution: dict[str, Any] = {
                "retriever": retriever,
                "rank": rank,
            }
            if has_score:
                contribution["score"] = score
                contribution["score_type"] = score_type
            contributions_by_id.setdefault(chunk_id, []).append(contribution)
            score_terms_by_id.setdefault(chunk_id, []).append(
                1.0 / (RRF_CONSTANT + rank)
            )

    fused = [
        {
            **chunks_by_id[chunk_id],
            "final_rank": 0,
            "final_score": math.fsum(score_terms_by_id[chunk_id]),
            "retrievers": sorted(
                contributions_by_id[chunk_id],
                key=lambda contribution: contribution["retriever"],
            ),
        }
        for chunk_id in chunks_by_id
    ]
    fused.sort(key=lambda result: (-result["final_score"], result["id"]))

    if top_k is not None:
        fused = fused[:top_k]

    for rank, result in enumerate(fused, start=1):
        result["final_rank"] = rank

    return fused
