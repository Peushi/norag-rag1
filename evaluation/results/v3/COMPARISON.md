# V3 Person A — BM25 and retrieval comparison

## Setup and relevance

Four real retrieval-only runs use the unchanged V2 question sets (baking: 10 answerable + 2 unanswerable; Kestrel: 8 + 2), 800-character chunks, 80-character overlap, MiniLM Dense embeddings and cosine distance. No Gemini calls, graph results, reranking, or distance threshold were used. Dense-only overall and per-type metrics exactly reproduce V2 800/80.

Hybrid uses Person C’s existing orchestrator and equal-weight RRF: sum of 1/(60+rank), deduplicate by chunk ID, ties by ascending ID. Each method returns up to 10 candidates; RRF produces the final top 10, whose prefixes are scored. API hybrid retrieval uses the same minimum candidate pool and then returns the requested final top-k.

Relevance requires the expected source and complete quote within a single chunk after whitespace normalization. Boundary-split quotes stay in the denominator and are flagged. Each quote is one evidence item; duplicate chunks cannot inflate evidence recovery. HitRate is the answerable-question fraction recovering any evidence; Recall is the mean per-question recovered/expected evidence fraction. Unanswerable questions are excluded. Scores measure quote recovery, not generated-answer correctness.

## BM25 design

- Reuses Words Analytics tokenization: Unicode words/numbers, casefolded, punctuation separated. KST-2044 becomes kst and 2044. No stemming, stopword removal, or external NLP libraries. Repeated query tokens are counted once; document repetitions affect TF.
- N and df refer to chunks, not original source files. IDF = log(1 + (N - df + 0.5)/(df + 0.5)).
- For each query term: score += IDF * tf * (k1 + 1)/(tf + k1 * (1 - b + b * chunk_length/average_chunk_length)), with k1=1.5 and b=0.75. Length is token count. Higher is better.
- Only positive-score chunks are returned. Unknown-only/punctuation-only questions and empty indexes return no chunks. Blank questions and invalid top-k raise ValueError. Equal scores sort by chunk ID.
- The in-memory index is rebuilt from current documents for every live BM25 request, and once per evaluation run. No cache, persistent sparse data, or new dependencies. This costs repeated tokenization but avoids stale data for these small corpora.
- Dense and BM25 use shared chunk_text and make_chunk_id. The live Dense guard fingerprints corpus text and chunk settings and rebuilds stale/legacy collections. Full rebuild metadata is published only after success. RRF also rejects same-ID content conflicts.
- Document selection is applied after full-corpus BM25 statistics, matching Dense’s index-wide statistics plus source filtering. Both None/all-documents and []/no-documents semantics are preserved. Cosine thresholds apply only to Dense, never to BM25 or fused scores.

## Overall metrics

Values are percentages.

| Corpus | Method | k | HitRate | Recall |
|---|---|---:|---:|---:|
| baking | dense | 1 | 50.00 | 17.50 |
| baking | dense | 3 | 100.00 | 72.50 |
| baking | dense | 5 | 100.00 | 79.17 |
| baking | dense | 10 | 100.00 | 84.17 |
| baking | dense_bm25 | 1 | 70.00 | 29.17 |
| baking | dense_bm25 | 3 | 90.00 | 53.33 |
| baking | dense_bm25 | 5 | 100.00 | 72.50 |
| baking | dense_bm25 | 10 | 100.00 | 90.83 |
| kestrel | dense | 1 | 62.50 | 40.62 |
| kestrel | dense | 3 | 87.50 | 81.25 |
| kestrel | dense | 5 | 87.50 | 81.25 |
| kestrel | dense | 10 | 100.00 | 93.75 |
| kestrel | dense_bm25 | 1 | 50.00 | 21.88 |
| kestrel | dense_bm25 | 3 | 87.50 | 71.88 |
| kestrel | dense_bm25 | 5 | 100.00 | 84.38 |
| kestrel | dense_bm25 | 10 | 100.00 | 93.75 |

## Per question type

Each cell is HitRate% / Recall%. The existing baking category other is preserved. Unanswerable types have no answerable denominator and null metrics.

| Corpus | Method | Type | n | k=1 | k=3 | k=5 | k=10 |
|---|---|---|---:|---|---|---|---|
| baking | dense | other | 7 | 42.86 / 14.29 | 100.00 / 69.05 | 100.00 / 78.57 | 100.00 / 85.71 |
| baking | dense | split_answer | 3 | 66.67 / 25.00 | 100.00 / 80.56 | 100.00 / 80.56 | 100.00 / 80.56 |
| baking | dense_bm25 | other | 7 | 57.14 / 21.43 | 85.71 / 45.24 | 100.00 / 69.05 | 100.00 / 90.48 |
| baking | dense_bm25 | split_answer | 3 | 100.00 / 47.22 | 100.00 / 72.22 | 100.00 / 80.56 | 100.00 / 91.67 |
| kestrel | dense | exact_identifier | 2 | 50.00 / 25.00 | 50.00 / 50.00 | 50.00 / 50.00 | 100.00 / 100.00 |
| kestrel | dense | split_answer | 2 | 100.00 / 62.50 | 100.00 / 100.00 | 100.00 / 100.00 | 100.00 / 100.00 |
| kestrel | dense | two_hop | 1 | 100.00 / 50.00 | 100.00 / 50.00 | 100.00 / 50.00 | 100.00 / 50.00 |
| kestrel | dense | versions | 2 | 0.00 / 0.00 | 100.00 / 100.00 | 100.00 / 100.00 | 100.00 / 100.00 |
| kestrel | dense | vocabulary | 1 | 100.00 / 100.00 | 100.00 / 100.00 | 100.00 / 100.00 | 100.00 / 100.00 |
| kestrel | dense_bm25 | exact_identifier | 2 | 50.00 / 25.00 | 50.00 / 50.00 | 100.00 / 100.00 | 100.00 / 100.00 |
| kestrel | dense_bm25 | split_answer | 2 | 100.00 / 37.50 | 100.00 / 62.50 | 100.00 / 62.50 | 100.00 / 100.00 |
| kestrel | dense_bm25 | two_hop | 1 | 100.00 / 50.00 | 100.00 / 50.00 | 100.00 / 50.00 | 100.00 / 50.00 |
| kestrel | dense_bm25 | versions | 2 | 0.00 / 0.00 | 100.00 / 100.00 | 100.00 / 100.00 | 100.00 / 100.00 |
| kestrel | dense_bm25 | vocabulary | 1 | 0.00 / 0.00 | 100.00 / 100.00 | 100.00 / 100.00 | 100.00 / 100.00 |

## Every answerable question

Each cell is Dense Recall% → Dense+BM25 Recall%. Unanswerable rows remain in raw output but have null retrieval metrics.

| Corpus | Question | Type | k=1 | k=3 | k=5 | k=10 |
|---|---|---|---|---|---|---|
| baking | B01 | other | 0.00 → 50.00 | 100.00 → 100.00 | 100.00 → 100.00 | 100.00 → 100.00 |
| baking | B02 | other | 0.00 → 33.33 | 33.33 → 33.33 | 100.00 → 33.33 | 100.00 → 100.00 |
| baking | B03 | other | 0.00 → 0.00 | 50.00 → 50.00 | 50.00 → 50.00 | 100.00 → 100.00 |
| baking | B04 | other | 0.00 → 0.00 | 100.00 → 0.00 | 100.00 → 100.00 | 100.00 → 100.00 |
| baking | B05 | split_answer | 50.00 → 50.00 | 100.00 → 100.00 | 100.00 → 100.00 | 100.00 → 100.00 |
| baking | B06 | other | 33.33 → 33.33 | 100.00 → 33.33 | 100.00 → 100.00 | 100.00 → 100.00 |
| baking | B07 | other | 33.33 → 0.00 | 33.33 → 33.33 | 33.33 → 33.33 | 33.33 → 66.67 |
| baking | B08 | split_answer | 0.00 → 66.67 | 66.67 → 66.67 | 66.67 → 66.67 | 66.67 → 100.00 |
| baking | B09 | split_answer | 25.00 → 25.00 | 75.00 → 50.00 | 75.00 → 75.00 | 75.00 → 75.00 |
| baking | B10 | other | 33.33 → 33.33 | 66.67 → 66.67 | 66.67 → 66.67 | 66.67 → 66.67 |
| kestrel | q01 | exact_identifier | 0.00 → 0.00 | 0.00 → 0.00 | 0.00 → 100.00 | 100.00 → 100.00 |
| kestrel | q02 | exact_identifier | 50.00 → 50.00 | 100.00 → 100.00 | 100.00 → 100.00 | 100.00 → 100.00 |
| kestrel | q03 | split_answer | 75.00 → 25.00 | 100.00 → 25.00 | 100.00 → 25.00 | 100.00 → 100.00 |
| kestrel | q04 | split_answer | 50.00 → 50.00 | 100.00 → 100.00 | 100.00 → 100.00 | 100.00 → 100.00 |
| kestrel | q05 | vocabulary | 100.00 → 0.00 | 100.00 → 100.00 | 100.00 → 100.00 | 100.00 → 100.00 |
| kestrel | q06 | versions | 0.00 → 0.00 | 100.00 → 100.00 | 100.00 → 100.00 | 100.00 → 100.00 |
| kestrel | q07 | versions | 0.00 → 0.00 | 100.00 → 100.00 | 100.00 → 100.00 | 100.00 → 100.00 |
| kestrel | q08 | two_hop | 50.00 → 50.00 | 50.00 → 50.00 | 50.00 → 50.00 | 50.00 → 50.00 |

## Improvements, regressions, and unchanged results

| Corpus | k | Improved Recall | Worsened Recall | Unchanged Recall |
|---|---:|---|---|---|
| baking | 1 | B01, B02, B08 | B07 | B03, B04, B05, B06, B09, B10 |
| baking | 3 | None | B04, B06, B09 | B01, B02, B03, B05, B07, B08, B10 |
| baking | 5 | None | B02 | B01, B03, B04, B05, B06, B07, B08, B09, B10 |
| baking | 10 | B07, B08 | None | B01, B02, B03, B04, B05, B06, B09, B10 |
| kestrel | 1 | None | q03, q05 | q01, q02, q04, q06, q07, q08 |
| kestrel | 3 | None | q03 | q01, q02, q04, q05, q06, q07, q08 |
| kestrel | 5 | q01 | q03 | q02, q04, q05, q06, q07, q08 |
| kestrel | 10 | None | None | q01, q02, q03, q04, q05, q06, q07, q08 |

## Concrete diagnoses

- **Kestrel q01:** the complete cause-and-two-IP passage moves from Dense rank 7 to BM25 rank 3 and fused rank 4. Thus Recall@5 improves 0% → 100%. It is still not first: generic runbook chunks match several query terms, and there is no identifier-specific boost.
- **Kestrel q08:** both methods together still recover only the runbook quote; catalog evidence remains absent in the final top 10. Recall stays 50%. Keywords alone do not supply the missing postroom → Messaging → channel hop. The expanded Graph evaluation also fails to retrieve the expected Service Catalog quote for q08 within the top 10.
- **Baking B04:** at 800/80, the two instructions move from Dense rank 3 to fused rank 4. Recall@3 drops 100% → 0%, while @5 remains 100%. The previous V2 400/40 ranks 6/7 remain historical; this main V3 experiment uses 800/80.
- **Baking B07:** the explanation quote moves from rank 1 to fused rank 3 (a Hit@1 regression), but the gravity-method quote enters at rank 9. Recall@10 improves 1/3 → 2/3. The chilling quote remains missing.
- **Kestrel q07:** current-policy evidence remains recovered within top 5. No prompt or policy labels were changed.

### Detailed fusion regression: Kestrel q03

Dense ranks billing-policy-2026.md position 5 first, recovering three of four expected quotes, and recovers all four by k=3. That chunk is absent from BM25’s top 10, so it receives only one RRF contribution (1/61 = 0.01639). Chunks present in both lists receive two contributions and outrank it. It falls to fused rank 8; Recall@5 drops 100% → 25%. Several promoted chunks concern the older 2025 policy. Equal-weight rank fusion does not know which policy is current. This is a measured retrieval regression, not a generated-answer claim.

| Fused rank | Chunk | Source | Original method ranks | RRF score |
|---:|---|---|---|---:|
| 1 | `5802397173f6::chunk_0004` | `billing-policy-2026.md` | bm25: 2, dense: 2 | 0.03225806 |
| 2 | `b748a9c48e16::chunk_0009` | `support-runbook-errors.md` | bm25: 1, dense: 4 | 0.03201844 |
| 3 | `d6d5fe300b8f::chunk_0003` | `billing-policy-2025.md` | bm25: 4, dense: 3 | 0.03149802 |
| 4 | `d6d5fe300b8f::chunk_0004` | `billing-policy-2025.md` | bm25: 6, dense: 6 | 0.03030303 |
| 5 | `b748a9c48e16::chunk_0010` | `support-runbook-errors.md` | bm25: 8, dense: 5 | 0.03009050 |
| 6 | `d6d5fe300b8f::chunk_0001` | `billing-policy-2025.md` | bm25: 9, dense: 7 | 0.02941813 |
| 7 | `5802397173f6::chunk_0002` | `billing-policy-2026.md` | bm25: 10, dense: 8 | 0.02899160 |
| 8 | `5802397173f6::chunk_0005` | `billing-policy-2026.md` | dense: 1 | 0.01639344 |

Baking B02 is another regression: Dense’s position-2 chunk has rank 5 but no BM25 top-10 contribution, so it falls to fused rank 8. Recall@5 drops from 100% to 1/3.

## Recommendation and dependencies

For the original eight-question Kestrel and original baking comparisons, keep Dense as the unchanged application default for now: it gives better Recall@3 on both corpora and better baking Recall@5. The expanded Kestrel comparison below is a separate experiment and shows a different result at intermediate cut-offs. Dense+BM25 is available as an explicit option: it improves Kestrel @5 identifier coverage and baking @10 evidence recall, but introduces the q03/B02/B04 regressions. No universal hybrid improvement is claimed; these are small fixed datasets.

Person B's Graph retriever and expanded Kestrel evaluation are now implemented and measured. The original V2 questions and evidence were left unchanged; q11 and q12 were added as provenance-labeled two-hop questions. The expanded set contains 10 answerable questions and 2 unanswerable questions. The original eight-question results above remain the historical Dense/BM25 comparison; the separate expanded results below include all 12 questions.

For Sasha: BM25 is registered behind existing /api/retrieve, /api/ask, and evaluation-run controls. Ranked BM25 results include id/text/source/position/rank/retriever/score/score_type. Hybrid responses use her unchanged fused schema and retain original ranks and score types. Candidate depth is at least 10 for hybrid fusion. The final evaluation runner now records per-adapter, retrieval/orchestration, and answer-generation latency. The existing precomputed results predate that instrumentation; rerun the evaluations before reporting latency values.

The existing precomputed V2 comparison endpoint still serves its original V2 files. This V3 folder is separate and is not silently substituted into that endpoint. No schema/frontend changes were made.


## Expanded Kestrel evaluation: Graph retrieval

This is a separate 12-question evaluation at 800-character chunks and 80-character overlap. It includes the original eight Kestrel questions, the two unanswerable questions, and the added q11/q12 two-hop questions. There are 10 answerable questions and 2 excluded unanswerable questions. Dense, Dense+BM25, and Dense+BM25+Graph use the same expanded question set. The graph configuration uses equal-weight RRF with k=60 and the same candidate/fusion evaluation approach. Metrics below are percentages.

### Overall expanded Kestrel metrics

| Method | k | HitRate | Recall |
|---|---:|---:|---:|
| Dense | 1 | 50.00 | 32.50 |
| Dense | 3 | 90.00 | 75.00 |
| Dense | 5 | 90.00 | 80.00 |
| Dense | 10 | 100.00 | 95.00 |
| Dense + BM25 | 1 | 50.00 | 22.50 |
| Dense + BM25 | 3 | 90.00 | 72.50 |
| Dense + BM25 | 5 | 100.00 | 82.50 |
| Dense + BM25 | 10 | 100.00 | 95.00 |
| Dense + BM25 + Graph | 1 | 60.00 | 27.50 |
| Dense + BM25 + Graph | 3 | 90.00 | 77.50 |
| Dense + BM25 + Graph | 5 | 100.00 | 87.50 |
| Dense + BM25 + Graph | 10 | 100.00 | 95.00 |

Graph gives the best overall Recall@3 and Recall@5 in this expanded Kestrel evaluation. Dense alone has the best Recall@1. All three configurations reach the same Recall@10. Therefore, Graph improves evidence coverage at intermediate cut-offs but is not uniformly best at every k.

### Two-hop question results

| Question | Dense Recall@3 / @5 | Dense + BM25 Recall@3 / @5 | Dense + BM25 + Graph Recall@3 / @5 |
|---|---:|---:|---:|
| q08 — KST-5031 escalation | 50% / 50% | 50% / 50% | 50% / 50% |
| q11 — ledger policy owner | 50% / 50% | 50% / 50% | 100% / 100% |
| q12 — KST-6010 escalation channel | 50% / 100% | 100% / 100% | 100% / 100% |

- **q08:** Every configuration retrieves the runbook evidence at rank 1, but none retrieves the expected Service Catalog quote within the top 10. Recall remains 50%. Graph does not solve this missing second-hop evidence.
- **q11:** Dense retrieves the two evidence quotes at ranks 3 and 7; Dense+BM25 at ranks 1 and 9; Graph at ranks 1 and 3. Graph is the only configuration to recover both quotes by k=3.
- **q12:** Dense retrieves the runbook and Service Catalog evidence at ranks 5 and 2. Dense+BM25 retrieves them at ranks 2 and 3. Graph retrieves them at ranks 1 and 2. Both hybrid configurations recover all evidence by k=3.

Across the three two-hop questions, Graph achieves HitRate@1 = 100% and Recall@3 = 83.33%, compared with Dense+BM25's HitRate@1 = 66.67% and Recall@3 = 66.67%, and Dense's HitRate@1 = 33.33% and Recall@3 = 50.00%. This is a small three-question subset, so it should be treated as evidence from this evaluation rather than a general guarantee for multi-hop queries.

### Graph interpretation and limitations

Graph contributes useful entity-relation paths for questions where the relevant information is spread across documents. The q11 and q12 results show improved ranking of the second-hop evidence. However, q08 remains unresolved: retrieving the postroom runbook passage does not guarantee retrieval of the Messaging contact details. The graph configuration should therefore be described as an improvement on two of the three tested two-hop questions, not as a complete solution to multi-hop retrieval.

The expanded results do not replace the original eight-question Dense/BM25 tables above. They are a separate comparison using the larger question set, so the two sets of aggregate figures should not be mixed.

The expanded raw results and summaries are:

- `kestrel_dense_800_80_12q.jsonl`
- `kestrel_dense_800_80_12q_summary.jsonl`
- `kestrel_dense_bm25_800_80_12q.jsonl`
- `kestrel_dense_bm25_800_80_12q_summary.jsonl`
- `kestrel_dense_bm25_graph_800_80_12q.jsonl`
- `kestrel_dense_bm25_graph_800_80_12q_summary.jsonl`

## Output fields and reproducibility

- Each run has a question JSONL and one summary JSONL. No original V2 result files were overwritten.
- Existing question labels, evidence_matches, retrieval_metrics, retrieved_chunks, evaluation_chunks, generation/grading fields, and legacy source-only retrieval_hit are retained.
- retriever_results stores each method’s ordered candidates and typed scores. fused_chunks stores actual RRF output. Hybrid evaluation_chunks add distance from the Dense candidate if present, otherwise null; BM25 scores are never represented as cosine distances. Dense-only evaluation_chunks keep the V2 representation.
- Summaries record method names, chunk settings, BM25 parameters, candidate depth, fusion policy, threshold scope, counts and metrics. Raw results contain original evidence/IDs, ranks, text and distances/scores.
- Tests: 84 passed, 0 failed, 0 skipped. Real API checks on both corpora matched the saved hybrid top five; selection and empty selection passed; Ask citation flow passed with a fake provider. Real evaluation used no retrieval mocks and no live Gemini calls.

Exact test command:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 backend/.venv/bin/python -m unittest discover -s backend -t . -p 'test_*.py' -v
```

Reproduce the four measurements with the environment activated (these overwrite only the matching V3 result files):

```bash
for dataset in baking kestrel; do
  python -m evaluation.rag_evaluation --dataset "$dataset" --retrievers dense --output "evaluation/results/v3/${dataset}_dense_800_80.jsonl"
  python -m evaluation.rag_evaluation --dataset "$dataset" --retrievers dense bm25 --output "evaluation/results/v3/${dataset}_dense_bm25_800_80.jsonl"
done
```

Alternative 400/40 configurations are supported by --chunk-size 400 --overlap 40 and tested for shared chunk identity. Live BM25 has no persistent cache to invalidate. No hidden /bm25 page was found, added, edited, or removed.
