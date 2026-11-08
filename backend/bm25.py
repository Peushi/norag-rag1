"""Small, rebuildable BM25 index over the same source chunks as Dense.

Uses Words Analytics tokenization: Unicode words/numbers, case-insensitive,
punctuation-separated (KST-2044 becomes kst and 2044). No stemming or stopwords.
Query terms are deduplicated. Corpus statistics are computed before source
filtering, so selecting documents does not change a chunk's score.
"""

import math
from collections import Counter

from backend.chunking import chunk_text
from backend.documents import load_documents
from backend.index_settings import validate_settings
from backend.retrieval import DATASET_DIRECTORIES, make_chunk_id
from backend.retrieval_orchestrator import RetrievalQuery, RetrieverOutput
from backend.words_analytics import tokenize

K1 = 1.5
B = 0.75


class BM25Index:
    """BM25 with positive Robertson IDF and standard length normalization.

    score = sum(log(1 + (N-df+0.5)/(df+0.5)) *
                tf*(k1+1)/(tf + k1*(1-b + b*length/average_length)))
    Higher scores are better. Only positive matches are returned; ties use ID.
    """

    def __init__(self, documents: list[dict], chunk_size: int = 800, overlap: int = 80):
        validate_settings(chunk_size, overlap)
        self.chunks = []
        self.term_counts = []
        self.document_frequency = Counter()
        self.lengths = []
        for document in documents:
            for chunk in chunk_text(document["text"], chunk_size, overlap):
                self.chunks.append({
                    "id": make_chunk_id(document["source"], chunk["position"]),
                    "text": chunk["text"],
                    "source": document["source"],
                    "position": chunk["position"],
                })
                counts = Counter(tokenize(chunk["text"]))
                self.term_counts.append(counts)
                self.document_frequency.update(counts.keys())
                self.lengths.append(sum(counts.values()))
        self.average_length = sum(self.lengths) / len(self.chunks) if self.chunks else 0

    def search(self, question: str, top_k: int = 5, selected_documents: list[str] | None = None) -> list[dict]:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("Question cannot be empty")
        if type(top_k) is not int or top_k < 1:
            raise ValueError("top_k must be a positive integer")
        if not self.chunks or not self.average_length or selected_documents == []:
            return []

        terms = set(tokenize(question))
        # Stable summation order also makes scores reproducible across processes.
        terms = sorted(terms & self.document_frequency.keys())
        selected = set(selected_documents) if selected_documents is not None else None
        results = []
        for chunk, counts, length in zip(self.chunks, self.term_counts, self.lengths):
            if selected is not None and chunk["source"] not in selected:
                continue
            score = 0.0
            for term in terms:
                tf = counts[term]
                if not tf:
                    continue
                df = self.document_frequency[term]
                idf = math.log(1 + (len(self.chunks) - df + 0.5) / (df + 0.5))
                score += idf * tf * (K1 + 1) / (
                    tf + K1 * (1 - B + B * length / self.average_length)
                )
            if score > 0:
                results.append({**chunk, "retriever": "bm25", "score": score, "score_type": "bm25"})

        results.sort(key=lambda chunk: (-chunk["score"], chunk["id"]))
        return [{**chunk, "rank": rank} for rank, chunk in enumerate(results[:top_k], 1)]


def retrieve_bm25(query: RetrievalQuery) -> RetrieverOutput:
    """Build a fresh in-memory index per request; no stale cache or disk data."""
    if query.dataset not in DATASET_DIRECTORIES:
        raise ValueError(f"Unknown retrieval dataset: {query.dataset}")
    index = BM25Index(
        load_documents(DATASET_DIRECTORIES[query.dataset]), query.chunk_size, query.overlap,
    )
    return RetrieverOutput(chunks=index.search(
        query.question, query.top_k,
        list(query.document_ids) if query.document_ids is not None else None,
    ))
