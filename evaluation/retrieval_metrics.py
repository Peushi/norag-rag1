"""Match full quotes in one chunk after collapsing whitespace.

Case and punctuation are preserved. Split quotes remain in the recall
denominator but are flagged and cannot match by joining chunk fragments.
"""

from backend.chunking import chunk_text

K_VALUES = (1, 3, 5, 10)


def score_at_k(evidence_matches: list[dict] | None) -> dict | None:
    """Score each required quote once, even if several chunks contain it."""
    if evidence_matches is None:
        return None
    if not evidence_matches:
        raise ValueError("Answerable questions must have expected evidence")

    scores = {}
    for k in K_VALUES:
        recovered = sum(
            any(chunk["rank"] <= k for chunk in evidence["matched_chunks"])
            for evidence in evidence_matches
        )
        scores[str(k)] = {
            "hit": bool(recovered),
            "recall": recovered / len(evidence_matches),
            "matched_evidence": recovered,
            "expected_evidence": len(evidence_matches),
        }
    return scores


def summarize_metrics(results: list[dict]) -> dict:
    """Average over answerable questions (macro recall), overall and per type.

    Unanswerable rows have retrieval_metrics=None and are excluded. With no
    answerable questions, metrics are None rather than a misleading zero.
    """
    def aggregate(rows):
        answerable = [row for row in rows if row["retrieval_metrics"] is not None]
        count = len(answerable)
        return {
            "answerable_questions": count,
            "excluded_questions": len(rows) - count,
            "metrics": {
                str(k): {
                    "hit_rate": sum(row["retrieval_metrics"][str(k)]["hit"] for row in answerable) / count if count else None,
                    "recall": sum(row["retrieval_metrics"][str(k)]["recall"] for row in answerable) / count if count else None,
                }
                for k in K_VALUES
            },
        }

    return {
        "overall": aggregate(results),
        "by_type": {
            kind: aggregate([row for row in results if row.get("type", "other") == kind])
            for kind in sorted({row.get("type", "other") for row in results})
        },
    }


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def match_evidence(
    question: dict,
    retrieved_chunks: list[dict],
    documents: list[dict],
    *,
    chunk_size: int,
    overlap: int,
) -> list[dict] | None:
    """Return per-evidence matches, or None for an unanswerable question.

    Ranks start at 1. Multiple chunks matching one evidence item are recorded,
    but that item still represents one required passage for subsequent recall.
    Source documents let us distinguish invalid labels from chunk boundaries.
    """
    if type(question.get("answerable")) is not bool:
        raise ValueError(f"Question {question.get('id')} needs a boolean answerable label")
    if question["answerable"] is False:
        if question.get("evidence"):
            raise ValueError(f"Unanswerable question {question.get('id')} must not have evidence")
        return None

    evidence = question.get("evidence", [])
    if not isinstance(evidence, list) or not evidence:
        raise ValueError(f"Question {question.get('id')} has no expected evidence")

    source_texts = {document["source"]: document["text"] for document in documents}
    source_chunks = {}
    matches = []
    for expected in evidence:
        if not isinstance(expected, dict) or not all(
            isinstance(expected.get(field), str) and expected[field].strip()
            for field in ("source", "quote")
        ):
            raise ValueError(f"Question {question.get('id')} needs a source and nonempty quote for each evidence item")
        source = expected["source"]
        quote = normalize_whitespace(expected["quote"])
        if not quote:
            raise ValueError(f"Question {question.get('id')} has an empty quote")
        if source not in source_texts or quote not in normalize_whitespace(source_texts[source]):
            raise ValueError(
                f"Question {question.get('id')}: quote not found in source {source}"
            )

        if source not in source_chunks:
            source_chunks[source] = [
                normalize_whitespace(chunk["text"])
                for chunk in chunk_text(source_texts[source], chunk_size, overlap)
            ]

        matched_chunks = [
            {"id": chunk["id"], "rank": rank}
            for rank, chunk in enumerate(retrieved_chunks, start=1)
            if chunk["source"] == source
            and quote in normalize_whitespace(chunk["text"])
        ]
        matches.append({
            "source": source,
            "quote": expected["quote"],
            "matched_chunks": matched_chunks,
            "boundary_split": not any(quote in text for text in source_chunks[source]),
        })

    return matches
