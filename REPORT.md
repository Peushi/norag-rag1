# BakeFix — V1 Report

BakeFix is a baking troubleshooting RAG application. V1 establishes a naive
baseline: retrieve passages from baking guides, then generate grounded answers
with source references.

## Team Responsibilities

| Member | Responsibilities |
|---|---|
| Karma Soliman | Document management, chunking, embeddings, ChromaDB indexing, retrieval, and retrieval evaluation |
| Peushi Ariyawansa | Gemini integration, grounded generation, Pydantic validation, and citation verification |
| Aleksandra Temereva | FastAPI routes, React frontend, shared API schema, integration, and error handling |

## Decision Log

### Karma — Indexing and Retrieval

| Decision | Choice and reason |
|---|---|
| Corpus | Baking troubleshooting guides, primarily from King Arthur Baking. Markdown preserves readable content and source information; the loader also supports `.txt`. |
| Chunking | Fixed-size windows of 800 characters with 80-character overlap: a simple, reproducible V1 baseline. |
| Embeddings | Local `all-MiniLM-L6-v2` (384 dimensions), avoiding hosted embedding API costs. The same model embeds documents and questions. |
| Vector storage | Persistent local ChromaDB stores text, embeddings, and metadata, with source-document filtering. |
| Retrieval | Cosine distance, where lower is closer; default top-k is 5. Optional relevance filtering is separate, with no fixed threshold chosen yet. |
| Shared output | Each result contains `id`, `text`, `source`, `position`, and `distance`, supporting citation verification and displaying retrieved evidence. |
| Index management | Full rebuilds after document or chunk-setting changes keep V1 simple for a small corpus. Chunk settings are saved for reuse. |
| Evaluation | Source-based Hit@5 checks whether at least one expected document appears among the top five chunks. Unanswerable questions are excluded. |

### Peushi — Answer Generation



### Aleksandra — API and Frontend



## Retrieval Baseline

Results from the recorded local run:

| Parameter | Value |
|---|---|
| Embedding model | `all-MiniLM-L6-v2` |
| Vector database / distance | ChromaDB / cosine |
| Chunk size / overlap | 800 / 80 characters |
| Top-k | 5 |
| Indexed documents / chunks | 10 / 68 |
| Evaluation questions | 6 answerable + 1 unanswerable |
| Source-based Hit@5 | 6/6 (100%) |

Reproduce after building the index:

```bash
python -m backend.evaluation
```


## Known Failures and Limitations

### Karma

- **Fixed boundaries:** Chunks can split words and explanations; overlap only partly reduces this.
- **Similarity versus evidence:** Nearest passages may not answer the question. Top-k retrieval can return unrelated chunks for an out-of-corpus question.
- **Evaluation coverage:** Six answerable questions are a small sample. Passage-level labels and a separate abstention check remain pending.
- **Rebuild recovery:** If indexing fails after resetting Chroma, restoring a document does not restore the previous index. Another rebuild may be needed.
- **Observed bug, fixed:** The first index build failed because deleting a missing collection raised `NotFoundError`; the handler now catches that exception.

### Peushi— Answer Generation



### Sasha — Integration and UI


