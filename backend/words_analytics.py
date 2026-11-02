from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from backend.chunking import chunk_text
from backend.documents import CORPUS_DIR, PROJECT_ROOT, load_documents
from backend.retrieval import make_chunk_id
from backend.schemas import EvaluationDataset

DEFAULT_CHUNK_SIZE = 800
DEFAULT_OVERLAP = 80

CORPUS_DIRECTORIES: dict[EvaluationDataset, Path] = {
    "baking": CORPUS_DIR,
    "kestrel": PROJECT_ROOT / "kestrel-kb" / "docs",
}

QUESTION_FILES: dict[EvaluationDataset, Path] = {
    "baking": PROJECT_ROOT / "evaluation" / "baking_questions.jsonl",
    "kestrel": PROJECT_ROOT / "kestrel-kb" / "eval" / "questions.starter.jsonl",
}

WORD_PATTERN = re.compile(r"[^\W_]+", flags=re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Return lowercase Unicode word/number tokens; punctuation separates words."""
    return [token.casefold() for token in WORD_PATTERN.findall(text)]


def _corpus_snapshot(
    dataset: EvaluationDataset,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> tuple[Counter[str], list[dict[str, Any]], dict[str, Counter[str]]]:
    documents = load_documents(CORPUS_DIRECTORIES[dataset])
    document_counts: Counter[str] = Counter()
    indexed_chunks: list[dict[str, Any]] = []
    counts_by_chunk: dict[str, Counter[str]] = {}

    for document in documents:
        document_counts.update(tokenize(document["text"]))
        for chunk in chunk_text(
            document["text"],
            chunk_size=chunk_size,
            overlap=overlap,
        ):
            indexed_chunks.append(
                {
                    "chunk_id": make_chunk_id(
                        document["source"],
                        chunk["position"],
                    ),
                    "source": document["source"],
                    "position": chunk["position"],
                    "text": chunk["text"],
                }
            )
            counts_by_chunk[indexed_chunks[-1]["chunk_id"]] = _word_counts(
                indexed_chunks[-1]
            )

    return document_counts, indexed_chunks, counts_by_chunk


def _word_counts(chunk: dict[str, Any]) -> Counter[str]:
    return Counter(tokenize(chunk["text"]))


def get_vocabulary(
    dataset: EvaluationDataset,
    *,
    query: str = "",
    limit: int = 500,
    offset: int = 0,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> dict[str, Any]:
    counts, _, counts_by_chunk = _corpus_snapshot(
        dataset,
        chunk_size=chunk_size,
        overlap=overlap,
    )
    chunk_counts: Counter[str] = Counter()

    for counts_for_chunk in counts_by_chunk.values():
        chunk_counts.update(counts_for_chunk.keys())

    normalized_query = query.casefold()
    words = [
        {
            "word": word,
            "occurrence_count": count,
            "chunk_count": chunk_counts[word],
        }
        for word, count in sorted(
            counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
        if normalized_query in word
    ]

    return {
        "dataset": dataset,
        "chunk_size": chunk_size,
        "overlap": overlap,
        "total_words": len(counts),
        "matching_words": len(words),
        "offset": offset,
        "words": words[offset : offset + limit],
    }


def get_word_chunks(
    dataset: EvaluationDataset,
    word: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> dict[str, Any]:
    normalized_word = word.casefold()
    chunks = []
    document_counts, indexed_chunks, counts_by_chunk = _corpus_snapshot(
        dataset,
        chunk_size=chunk_size,
        overlap=overlap,
    )

    for chunk in indexed_chunks:
        count = counts_by_chunk[chunk["chunk_id"]].get(normalized_word, 0)
        if count:
            chunks.append(
                {
                    **chunk,
                    "occurrence_count": count,
                    "matched_words": [normalized_word],
                }
            )

    return {
        "dataset": dataset,
        "chunk_size": chunk_size,
        "overlap": overlap,
        "word": normalized_word,
        "occurrence_count": document_counts[normalized_word],
        "chunk_count": len(chunks),
        "chunks": chunks,
    }


def analyze_question(
    dataset: EvaluationDataset,
    question: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> dict[str, Any]:
    question_words = list(dict.fromkeys(tokenize(question)))
    per_word_chunks: dict[str, list[dict[str, Any]]] = {}
    word_entries = []
    document_counts, chunks, counts_by_chunk = _corpus_snapshot(
        dataset,
        chunk_size=chunk_size,
        overlap=overlap,
    )

    for word in question_words:
        matching_chunks = []
        for chunk in chunks:
            count = counts_by_chunk[chunk["chunk_id"]].get(word, 0)
            if count:
                matching_chunks.append(
                    {
                        **chunk,
                        "occurrence_count": count,
                        "matched_words": [word],
                    }
                )

        per_word_chunks[word] = matching_chunks
        if document_counts[word]:
            word_entries.append(
                {
                    "word": word,
                    "occurrence_count": document_counts[word],
                    "chunk_count": len(matching_chunks),
                }
            )

    missing_words = [
        word for word in question_words if not per_word_chunks[word]
    ]
    combined_chunks: dict[str, dict[str, Any]] = {}
    for word, word_chunks in per_word_chunks.items():
        for chunk in word_chunks:
            existing = combined_chunks.get(chunk["chunk_id"])
            if existing is None:
                combined_chunks[chunk["chunk_id"]] = {
                    **chunk,
                    "matched_words": [word],
                }
            else:
                existing["occurrence_count"] += chunk["occurrence_count"]
                existing["matched_words"].append(word)

    return {
        "dataset": dataset,
        "chunk_size": chunk_size,
        "overlap": overlap,
        "words_found": word_entries,
        "words_missing": missing_words,
        "matching_chunks": sorted(
            combined_chunks.values(),
            key=lambda chunk: (
                -len(chunk["matched_words"]),
                -chunk["occurrence_count"],
                chunk["source"],
                chunk["position"],
            ),
        ),
    }


def list_questions(dataset: EvaluationDataset) -> list[dict[str, str]]:
    path = QUESTION_FILES[dataset]
    questions = []
    with path.open("r", encoding="utf-8-sig") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                question = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid question JSON at {path}:{line_number}"
                ) from exc

            if not isinstance(question, dict):
                raise ValueError(f"Question at {path}:{line_number} must be an object.")
            if not isinstance(question.get("id"), str) or not isinstance(
                question.get("question"), str
            ):
                raise ValueError(
                    f"Question at {path}:{line_number} requires string id and question."
                )

            question_type = question.get("type", "other")
            questions.append(
                {
                    "id": question["id"],
                    "question": question["question"],
                    "type": question_type if isinstance(question_type, str) else "other",
                }
            )
    return questions
