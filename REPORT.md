# BakeFix — V1 and V2 Report

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



## V2 — Retrieval Evaluation and Words Analytics

### Objective

V2 focuses on evaluating retrieval quality rather than simply checking whether the correct source document appears in the results.

We evaluated two corpora, Baking and Kestrel KB, using the same question sets and embedding model across two chunking configurations. The goal was to measure evidence retrieval, compare configurations, and understand failures using Words Analytics.

### Karma — Retrieval and Evaluation

#### Decision Log

| Decision | Alternatives considered | Choice and justification |
|---|---|---|
| Relevance measurement | Source-level matching vs. supporting-passage matching | We moved to source-and-quote matching because retrieving the correct document does not guarantee that the answer is retrieved. |
| Metrics | A single HitRate@5 vs. multiple retrieval measurements | We measure HitRate and Recall at k = 1, 3, 5, and 10, including results per question type. Recall also captures incomplete evidence retrieval. |
| Configurations | Keep 800/80 vs. experiment with smaller chunks | We compared 800/80 and 400/40 to measure how chunk size affects retrieval. |
| Evaluation | Generate answers for every question vs. retrieval-only evaluation | Retrieval-only is the default to evaluate retrieval independently without unnecessary Gemini calls. |
| Evidence matching | Allow partial quotations vs. require a complete supporting quote | We require the complete quote within one chunk, with whitespace normalization. Split quotations are flagged as a limitation. |

#### Retrieval Results

Both corpora were evaluated using `all-MiniLM-L6-v2`, cosine distance, unchanged question sets, and no relevance threshold.

| Corpus | Configuration | HitRate@5 | Recall@5 |
|---|---|---:|---:|
| Baking | 800/80 | 100% | 79.2% |
| Baking | 400/40 | 70% | 44.2% |
| Kestrel | 800/80 | 87.5% | 81.3% |
| Kestrel | 400/40 | 75% | 71.9% |

**HitRate@k** measures the proportion of answerable questions for which at least one expected supporting passage is retrieved in the top k.

**Recall@k** measures the proportion of expected passages recovered for each answerable question, averaged across questions.

Unanswerable questions are excluded from both metrics.

The 800/80 configuration performed better overall across both corpora. Smaller chunks reduced retrieval quality, partly because some expected quotations crossed chunk boundaries.

We therefore retained 800/80 as our preferred configuration among those tested. However, some individual questions improved with 400/40, showing that the larger configuration is not universally better.

Complete results at k = 1, 3, 5, and 10, including per-question-type measurements, are available in [the retrieval comparison](evaluation/results/retrieval_comparison.md).

#### Observed Failures and Words Analysis

**1. Kestrel q01 — Exact identifier retrieval**

The question asks about error `KST-2044`. The required passage contains both IP addresses needed to resolve the error.

With 800/80, the passage ranked seventh, meaning top-5 retrieval missed both expected quotations.

Words Analytics showed that the exact identifier `2044` appears in the correct chunk but not in the five higher-ranked chunks. Meanwhile, more general words such as `kst` occur across multiple runbook chunks.

This suggests that semantic ranking did not sufficiently prioritize the distinguishing identifier, although the vocabulary analysis does not establish the embedding model's internal cause.

**2. Baking B04 — Flour measurement instructions**

The question asks how to measure flour without a scale.

With 400/40, the two expected instructions ranked sixth and seventh, despite the five higher-ranked chunks coming from the correct document.

Words Analytics showed that common terms such as `flour` and `cup` appeared in many chunks. Their presence alone did not distinguish the specific instructions from general flour-measurement information.

With 800/80, both expected passages appeared together at rank three.

This demonstrates how chunk size can affect the amount of useful context retrieved.

Additional failures, including Kestrel q08 and Baking B07, are documented in [the retrieval miss diagnoses](evaluation/results/retrieval_miss_diagnoses.md).

#### Verification

The four evaluation runs produced reproducible results, and 22 automated tests passed after Words Analytics integration.

Evaluation was performed without live Gemini calls, allowing retrieval quality to be measured separately from answer generation.

#### Remaining Limitations

- Exact-quote matching is reproducible but does not capture every useful paraphrase.
- Some required evidence can be divided across chunk boundaries.
- Retrieving one supporting passage does not guarantee that all evidence needed for a complete answer is available.
- Semantic similarity does not guarantee relevance, particularly for exact identifiers and multi-document questions.
- Answer correctness and abstention quality require separate generation-side evaluation.

These findings provide directions for future retrieval improvements.

### Peushi — LLM Evaluation and Answer Quality

*To be completed by Peushi.*

### Aleksandra — Words Analytics and Frontend Integration

*To be completed by Aleksandra.*
