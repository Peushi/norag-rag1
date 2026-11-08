# BakeFix — V1, V2 and V3 Report

BakeFix is a baking troubleshooting RAG application. V1 establishes a naive
baseline: retrieve passages from baking guides, then generate grounded answers
with source references.

## Team Responsibilities

| Member              | Responsibilities                                                                                  |
| ------------------- | ------------------------------------------------------------------------------------------------- |
| Karma Soliman       | Document management, chunking, embeddings, ChromaDB indexing, retrieval, and retrieval evaluation |
| Peushi Ariyawansa   | Gemini integration, grounded generation, Pydantic validation, and citation verification           |
| Aleksandra Temereva | FastAPI routes, React frontend, shared API schema, integration, and error handling                |

## Decision Log

### Karma — Indexing and Retrieval

| Decision         | Choice and reason                                                                                                                                              |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Corpus           | Baking troubleshooting guides, primarily from King Arthur Baking. Markdown preserves readable content and source information; the loader also supports `.txt`. |
| Chunking         | Fixed-size windows of 800 characters with 80-character overlap: a simple, reproducible V1 baseline.                                                            |
| Embeddings       | Local `all-MiniLM-L6-v2` (384 dimensions), avoiding hosted embedding API costs. The same model embeds documents and questions.                                 |
| Vector storage   | Persistent local ChromaDB stores text, embeddings, and metadata, with source-document filtering.                                                               |
| Retrieval        | Cosine distance, where lower is closer; default top-k is 5. Optional relevance filtering is separate, with no fixed threshold chosen yet.                      |
| Shared output    | Each result contains `id`, `text`, `source`, `position`, and `distance`, supporting citation verification and displaying retrieved evidence.                   |
| Index management | Full rebuilds after document or chunk-setting changes keep V1 simple for a small corpus. Chunk settings are saved for reuse.                                   |
| Evaluation       | Source-based Hit@5 checks whether at least one expected document appears among the top five chunks. Unanswerable questions are excluded.                       |

### Aleksandra — API and Frontend

| Decision               | Choice and reason                                                                                                                                                               |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Client/server boundary | A React frontend communicates with the FastAPI backend over JSON endpoints, keeping retrieval and generation logic on the server.                                               |
| Shared contract        | Pydantic request and response models define and validate the API payloads so the frontend can rely on consistent answer, retrieval, and document shapes.                        |
| User workflow          | The UI separates document management, retrieval settings, and question answering. Users can inspect the retrieved evidence alongside the generated answer to check its sources. |
| Search configuration   | Chunk size, overlap, and top-k are configurable through the settings endpoint, allowing users to tune retrieval without changing the client or server code.                     |
| Failure handling       | The API returns explicit validation and not-found errors, and the frontend displays failures to users rather than presenting them as successful empty results.                  |

## Retrieval Baseline

Results from the recorded local run:

| Parameter                  | Value                         |
| -------------------------- | ----------------------------- |
| Embedding model            | `all-MiniLM-L6-v2`            |
| Vector database / distance | ChromaDB / cosine             |
| Chunk size / overlap       | 800 / 80 characters           |
| Top-k                      | 5                             |
| Indexed documents / chunks | 10 / 68                       |
| Evaluation questions       | 6 answerable + 1 unanswerable |
| Source-based Hit@5         | 6/6 (100%)                    |

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

| Decision              | Choice and reason                                                                                                                                                             |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| LLM integration       | Google Gemini through the OpenAI-compatible API, keeping model configuration in environment variables.                                                                        |
| Prompt construction   | A grounded prompt provides the user's question and retrieved passages as context. The model is instructed to answer using the supplied evidence and avoid unsupported claims. |
| Response validation   | Pydantic schemas validate the generated response structure and ensure references correspond to retrieved chunks.                                                              |
| Citation verification | References are checked against the retrieved chunk IDs to prevent invalid citations.                                                                                          |
| Abstention            | When the retrieved evidence is insufficient, the system returns a `not_found` response rather than inventing an answer.                                                       |
| Evaluation            | Created reusable no-context and RAG evaluation workflows, JSONL result files, and manual-review tools to assess answer quality.                                               |

### Peushi — Known Limitations

- **Retrieval dependency:** Answer quality depends on whether the retriever provides the correct evidence.
- **LLM variability:** Generated responses may vary between runs.
- **Context limitations:** Missing or incomplete evidence can lead to an abstention even when the answer exists elsewhere in the corpus.
- **Citation limitations:** Valid citation IDs do not automatically guarantee that the cited passage fully supports the answer

### Aleksandra — Integration and UI

The V1 integration connects the React client to the FastAPI backend through a
shared JSON API contract. Pydantic request and response models validate the
main retrieval and answer payloads, including answer references to retrieved
chunk IDs.

| Area                  | Implementation                                                                                                                                                                                                                                                                                           |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Ask flow              | The Ask view accepts a question, lets users select documents and configure chunk size, overlap, and top-k, then displays the generated answer, abstention, or an actionable error state.                                                                                                                 |
| Evidence display      | Retrieved evidence is shown with its source, position, and quote so users can check the answer against the indexed notes.                                                                                                                                                                                |
| Document management   | The document library lists available notes and supports uploading UTF-8 `.md` and `.txt` files and removing documents. Upload, delete, and validation failures are surfaced in the UI.                                                                                                                   |
| API integration       | `GET /api/documents`, `POST /api/documents`, `DELETE /api/documents/{document_id}`, and `PUT /api/settings` support the library and search settings. `POST /api/retrieve` returns retrieved chunks; `POST /api/ask` runs retrieval and answer generation; `GET /api/chunks/{chunk_id}` looks up a chunk. |
| Errors and validation | Invalid requests return explicit API errors, and the frontend displays request failures rather than silently presenting them as empty or successful results.                                                                                                                                             |

## V2 — Retrieval Evaluation and Words Analytics

### Objective

V2 focuses on evaluating retrieval quality rather than simply checking whether the correct source document appears in the results.

We evaluated two corpora, Baking and Kestrel KB, using the same question sets and embedding model across two chunking configurations. The goal was to measure evidence retrieval, compare configurations, and understand failures using Words Analytics.

### Karma — Retrieval and Evaluation

#### Decision Log

| Decision              | Alternatives considered                                           | Choice and justification                                                                                                                       |
| --------------------- | ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Relevance measurement | Source-level matching vs. supporting-passage matching             | We moved to source-and-quote matching because retrieving the correct document does not guarantee that the answer is retrieved.                 |
| Metrics               | A single HitRate@5 vs. multiple retrieval measurements            | We measure HitRate and Recall at k = 1, 3, 5, and 10, including results per question type. Recall also captures incomplete evidence retrieval. |
| Configurations        | Keep 800/80 vs. experiment with smaller chunks                    | We compared 800/80 and 400/40 to measure how chunk size affects retrieval.                                                                     |
| Evaluation            | Generate answers for every question vs. retrieval-only evaluation | Retrieval-only is the default to evaluate retrieval independently without unnecessary Gemini calls.                                            |
| Evidence matching     | Allow partial quotations vs. require a complete supporting quote  | We require the complete quote within one chunk, with whitespace normalization. Split quotations are flagged as a limitation.                   |

#### Retrieval Results

Both corpora were evaluated using `all-MiniLM-L6-v2`, cosine distance, unchanged question sets, and no relevance threshold.

| Corpus  | Configuration | HitRate@5 | Recall@5 |
| ------- | ------------- | --------: | -------: |
| Baking  | 800/80        |      100% |    79.2% |
| Baking  | 400/40        |       70% |    44.2% |
| Kestrel | 800/80        |     87.5% |    81.3% |
| Kestrel | 400/40        |       75% |    71.9% |

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

#### Objective

My work focused on evaluating Gemini's answer quality with and without retrieved context, checking whether answers were correct, grounded, and properly supported by references.

#### Implementation Decisions

- **LLM integration:** Integrated Google Gemini through the OpenAI-compatible API.
- **Prompt engineering:** Created prompts that instruct Gemini to answer using retrieved evidence and avoid unsupported claims.
- **Validation:** Used Pydantic to validate response structures and verify that citation IDs match retrieved chunks.
- **Abstention:** Implemented `not_found` responses when the available evidence is insufficient.
- **Evaluation:** Created reusable RAG and no-context evaluation scripts, JSONL result files, and manual-review tools.

#### Evaluation Results

| Corpus | Evaluation | Correct | Partial | Wrong |
|---|---|---:|---:|---:|
| Baking | RAG | 10 + 2 correct refusals | 0 | 0 |
| Baking | No-context | 6 | 6 | 0 |
| Kestrel | RAG | 7 | 1 | 2 |
| Kestrel | No-context | 1 | 1 | 8 |

The results show that providing retrieved context improved answer quality, especially for the Kestrel knowledge base.

#### Observed Failures and Limitations

- **Missing evidence:** Kestrel q01 and q08 demonstrated that missing or incomplete retrieved passages can lead to incorrect or incomplete answers.
- **Prompt improvement:** Refining the prompt resolved an initial Kestrel q07 billing-policy interpretation issue; the retest correctly identified the 20% annual discount.
- **LLM variability:** Answers may vary between runs.
- **Evaluation limitations:** Manual assessment involves some subjectivity, and the datasets are relatively small.
- **Citation limitations:** Valid citation IDs do not necessarily guarantee that the cited passages fully support the generated answer.

Overall, the evaluation showed that RAG improves answer quality compared with generation without context, but reliable answers still depend on retrieving sufficient evidence.

### Aleksandra — Words Analytics and Frontend Integration

#### Decisions and Implementation

| Area                 | Decision and implementation                                                                                                                                                                                                                                                                                                                                           |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Corpus selection     | Words Analytics uses the shared `baking` and professor-provided `kestrel` corpora. It reuses the backend document loader rather than maintaining a separate corpus copy or index.                                                                                                                                                                                     |
| Chunk consistency    | The service calls the same `chunk_text()` implementation and chunk-ID helper used by retrieval. The default is 800/80; users can select other valid chunk sizes and overlaps, including the 400/40 comparison setting.                                                                                                                                                |
| Word matching        | Matching is case-insensitive and uses Unicode word/number tokens, with punctuation as a separator. For example, `KST-2044` becomes `kst` and `2044`. The same tokenizer is applied to source text, chunks, and questions.                                                                                                                                             |
| Count semantics      | Corpus occurrence totals are counted once from source documents. Distinct chunk counts and per-chunk occurrences are reported separately; because chunks overlap, summing per-chunk occurrences can exceed the source total.                                                                                                                                          |
| Frontend integration | The React application provides Ask, Words, and Evaluation views. Words supports corpus vocabulary search and pagination, selected-word chunk inspection, fixed question sets, and freeform or saved-question analysis. Evaluation retains the asynchronous answer-generation runner and displays the separate retrieval comparison.                                   |
| API contracts        | FastAPI response models validate the Words and retrieval-comparison payloads. The frontend also checks response shapes and presents request failures instead of treating invalid responses as successful results.                                                                                                                                                     |
| Retrieval comparison | A dedicated endpoint serves precomputed retrieval-only results, separate from answer-generation runs: `/api/evaluations/retrieval/retrieval-v2-baking/results` and `/api/evaluations/retrieval/retrieval-v2-kestrel/results`. It includes both configurations, aggregate metrics, question-type breakdowns, and per-question evidence and ranked evaluation passages. |

#### Verification

- Words Analytics tests cover source-versus-chunk counts, overlapping chunks, case and punctuation normalization, and identifiers such as `KST-2044`.
- Retrieval-comparison tests check both datasets and chunk configurations, aggregate metrics, question-type results, per-question ranks, null metrics for unanswerable questions, and unknown experiment handling.
- The focused backend test set passed (26 tests), and the frontend passed TypeScript typechecking and a production build.

#### Limitations

- Words Analytics reloads and rechunks the selected corpus for requests rather than maintaining a separate cached index. This keeps its chunks aligned with retrieval; larger corpora may benefit from measured caching later.
- Vocabulary matching is exact after normalization; it does not perform stemming, synonym matching, or semantic search.
- The retrieval-comparison endpoint serves the committed, precomputed experiment files. It does not calculate new passage-level comparisons for arbitrary configurations.
- Evidence labels and retrieval metrics describe recovery of the supplied expected quotes. They do not measure generated-answer correctness or establish that a retrieved passage supports every part of an answer.

## V3 — Hybrid Retrieval and Knowledge Graph

### Peushi — Knowledge Graph Construction and Path as Context

#### Graph Extraction and Build Statistics

A knowledge graph was constructed for the Kestrel knowledge base using Gemini-based graph extraction. The extraction process used the existing document chunking configuration (800 characters per chunk, with an overlap of 80 characters).

The graph extraction process produced the following results:

| Metric | Result |
|---|---:|
| Documents processed | 5 |
| Chunks processed | 43 |
| Successful Gemini calls | 43 |
| Failed chunks | 0 |
| Valid graph triples | 32 |
| Invalid triples | 3 |
| Prompt tokens | 21,857 |
| Completion tokens | 4,438 |
| Total tokens | 26,295 |
| Total build time | 297.23 seconds |
| Retry time | 109.79 seconds |

All 43 chunks were processed successfully. Three extracted triples were recorded as invalid because their evidence quotes did not pass the validation checks. Valid triples were stored with their supporting chunk references so that graph relationships could be traced back to the original documentation.

#### Graph Quality Review

A deterministic random sample of 10 extracted triples (seed 42) was manually reviewed. Each triple was classified as correct, incorrect, or unsupported based on its supporting evidence.

| Classification | Count | Percentage |
|---|---:|---:|
| Correct | 6 | 60% |
| Incorrect | 1 | 10% |
| Unsupported | 3 | 30% |

The review showed that most sampled relationships were correct, but some extracted relationships were not sufficiently supported by their evidence. For example, the extracted relationship identifying Payments Core as a SERVICE was incorrect: Payments Core represents a TEAM. This entity type was subsequently corrected in the graph.

Some SUPPORTS relationships were also classified as unsupported because the source text described which plans a policy applied to without explicitly establishing the claimed support relationship.

These results represent a sample of 10 triples, not a complete evaluation of all 32 graph triples.

#### Entity Resolution

Entity resolution was implemented to handle historical aliases and prevent incorrect entity merges.

One confirmed resolution maps the historical SERVICE alias `mailman` to the current SERVICE entity `postroom`. The service catalogue indicates that postroom replaced mailman and that older references should be interpreted as referring to postroom.

A potentially incorrect merge was also explicitly rejected: `Identity` as a SERVICE was kept separate from `Identity` as a TEAM. Although the names are identical, their entity types represent different concepts.

This helps preserve graph consistency and avoids combining entities simply because they share the same name.

#### Path as Context Evaluation

The Path as Context approach was implemented to provide Gemini with relevant graph paths alongside their supporting document chunks. Graph paths are used as additional navigation context, while the original document chunks remain the source of evidence for generated answers.

Two Kestrel questions were tested by comparing Gemini responses with and without graph paths.

| Question | Without graph | With graph |
|---|---|---|
| Which team owns the service responsible for KST-5031? | Correct answer | Correct answer |
| If more than three customers are affected by KST-6010 on the same day, which team should support escalate to, and which channel should they use? | Correct answer | Correct answer |

For the KST-5031 question, both configurations returned the correct team and supporting references. The measured response times were 0.96 seconds without graph context and 0.98 seconds with graph context.

For KST-6010, the graph initially failed to connect the escalation target to its on-call channel because Payments Core had an inconsistent entity type across the extracted triples. After correcting Payments Core to the TEAM entity type, graph retrieval successfully returned the two-hop path:

`KST-6010 → Payments Core → #oncall-payments`

Both configurations then produced the correct answer and cited the supporting runbook and service catalogue. The response time was 2.28 seconds without graph context and 2.00 seconds with graph context.

The results show that graph paths can make multi-hop relationships explicit. However, they did not improve answer correctness in these two experiments because the retrieved document chunks already contained the necessary information. The measured latency differences are based on individual runs and are not sufficient to establish a performance improvement.

#### Limitations

- The manual graph quality review covered only 10 of the 32 valid triples. A larger review would be needed to estimate overall graph quality reliably.
- Three extracted triples failed evidence-quote validation, showing that graph extraction is not completely reliable.
- Entity resolution currently relies on explicit mappings and entity-type checks. More complex aliases and ambiguous entities may require additional review.
- The Path as Context experiment covered only two questions. More two-hop questions and repeated runs are needed before drawing conclusions about answer quality or latency.
- Gemini output and response times may vary between runs.
- Graph paths do not replace source evidence. Their supporting document chunks must remain available to the answer-generation process.

## V3 — Karma: BM25 and Retrieval Evaluation

### Design decisions

- BM25 uses the same documents, character chunks, IDs, and Words Analytics
  tokenizer as Dense: casefolded Unicode words/numbers, punctuation separated
  (`KST-2044` → `kst`, `2044`), no stemming or stopword removal.
- Standard BM25 uses positive Robertson IDF, term-frequency saturation, and token
  length normalization with **k1=1.5, b=0.75**. Query terms are deduplicated;
  repeated document terms affect TF. Higher scores rank first; ties use chunk ID.
  Zero-score chunks are omitted. No new dependencies were added.
- The BM25 index lives in memory and is rebuilt from current sources per live
  request, once per evaluation. This is cheap for these corpora and avoids stale
  sparse indexes after additions, deletion, content edits, or setting changes.
- Dense checks a corpus-content/settings fingerprint and rebuilds stale indexes
  before search, keeping fusion consistent. Hybrid retrieval uses Person C's
  unchanged, equally weighted RRF (constant 60), with at least 10 candidates per
  method and then the requested final top-k. Scores retain their original types.

### Measured results

Four real retrieval-only runs used original V2 questions, MiniLM, cosine Dense,
800/80 chunks, and no threshold. The Dense results reproduce V2 exactly.

| Corpus | Method | HitRate@5 | Recall@5 | Recall@10 |
|---|---|---:|---:|---:|
| Baking | Dense | 100% | 79.17% | 84.17% |
| Baking | Dense + BM25 | 100% | 72.50% | 90.83% |
| Kestrel | Dense | 87.50% | 81.25% | 93.75% |
| Kestrel | Dense + BM25 | 100% | 84.38% | 93.75% |

Source-plus-complete-quote relevance, boundary handling, macro Recall, all four
k values, and unanswerable exclusion remain unchanged. Raw per-question results,
summaries, all-k/per-type tables, and reproduction commands are in
[the V3 comparison](evaluation/results/v3/COMPARISON.md).

### Improvements and regressions

- **q01:** complete two-IP evidence moves from Dense rank 7 to BM25 rank 3 and
  fused rank 4, fixing the top-5 miss.
- **q08:** catalog evidence is still missing; Recall remains 50% at k=10.
- **B07:** Recall@10 improves from 1/3 to 2/3, but its first evidence moves from
  rank 1 to 3. **B04** moves from rank 3 to 4, worsening Hit@3.
- **q03 regression:** the current-policy chunk is Dense rank 1 but absent from
  BM25's top 10. Chunks returned by both methods gain two RRF contributions and
  push it to rank 8; Recall@5 falls from 100% to 25%. **B02** similarly falls from
  100% to 1/3 at k=5. Thus hybrid does not always improve evidence coverage.

Keep Dense as the current default: Recall@3 is better on both corpora and baking
Recall@5 is higher. Hybrid is available for explicit comparison and improves
Kestrel identifier coverage at k=5 and baking coverage at k=10. Small question
sets and exact-quote labels limit generalization.

### Verification and remaining dependencies

All **84 tests passed**, with no failures or skips. Real hybrid API checks matched
the evaluation's top-five IDs on both corpora. Index edits, chunk-setting changes,
selection, empty results, and citation compatibility were checked; provider calls
were mocked only for generation checks. No live Gemini calls were made.

Graph retrieval is not registered, so Dense + BM25 + Graph measurements remain
pending Person B. Kestrel still has only original q08 labeled `two_hop`; the two
additional questions need team coordination with evidence for every hop. Original
questions, Person B's prompt/Path as Context work, and Person C's RRF/UI were
preserved. Shared latency collection remains Person C's responsibility. The hidden
`/bm25` page is absent and was not implemented or changed.
