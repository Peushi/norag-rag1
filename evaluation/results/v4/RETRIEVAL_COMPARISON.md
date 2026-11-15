# V4 retrieval comparison 

The five configurations repeat the V3 comparison at 800-character chunks,
80-character overlap, MiniLM `all-MiniLM-L6-v2`, cosine Dense, top-k=5,
no distance threshold and no question limit. Hybrid candidate depth is 10 per
retriever; RRF uses constant 60 and equal weights. The same fixed labels and
full 12-question sets are used for each dataset (10 answerable, 2 excluded).

## Results

Values are percentages. Every overall and per-question-type metric exactly
matches its corresponding V3 result; V4 changes do not establish a retrieval
improvement or degradation on these fixed tests.

| Dataset | Method | Hit@1 | Recall@1 | Hit@3 | Recall@3 | Hit@5 | Recall@5 | Hit@10 | Recall@10 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baking | Dense | 50.00 | 17.50 | 100.00 | 72.50 | 100.00 | 79.17 | 100.00 | 84.17 |
| Baking | Dense + BM25 | 70.00 | 29.17 | 90.00 | 53.33 | 100.00 | 72.50 | 100.00 | 90.83 |
| Kestrel | Dense | 50.00 | 32.50 | 90.00 | 75.00 | 90.00 | 80.00 | 100.00 | 95.00 |
| Kestrel | Dense + BM25 | 50.00 | 22.50 | 90.00 | 72.50 | 100.00 | 82.50 | 100.00 | 95.00 |
| Kestrel | Dense + BM25 + Graph | 60.00 | 27.50 | 90.00 | 77.50 | 100.00 | 87.50 | 100.00 | 95.00 |

HitRate@k is the mean of question-level hits (at least one expected evidence
item recovered). Recall@k is macro-averaged evidence recovery. Relevance
requires the expected source and complete supporting quote in one chunk after
whitespace normalization. Unanswerable questions are excluded from both metrics;
retrieval coverage does not measure answer correctness.

The q01 identifier improvement and q08 miss remain: Kestrel Dense+BM25 recovers
q01's complete expected evidence within five results, while q08 still lacks the
expected catalogue evidence and has 50% Recall@10. Graph improves some two-hop
rankings but does not resolve that miss. Existing V3 regression diagnoses remain
valid; hybrid retrieval is not universally better.

## Machine-readable records

- [retrieval_comparison.jsonl](retrieval_comparison.jsonl): all 60 per-question
  records, retaining original runner fields, retrieved chunks, ranks, native and
  fused results, evidence matches and all-k metrics. Group by
  `evaluation_config.dataset` and `evaluation_config.configuration_id`.
- [retrieval_comparison_summary.jsonl](retrieval_comparison_summary.jsonl): five
  complete runner summaries, including overall and per-type metrics. Group by
  `dataset` and `configuration_id`.

The bundled records are byte-content-equivalent JSON objects to the isolated
runner outputs; consolidating them avoids ten separate raw/summary files.
They contain only the fixed public/fictional evaluation questions and corpus
passages already tracked in the project, not user uploads, prompts, provider
keys, traces or generated answers. Observed timing fields are retained as
single local-run measurements, not a controlled performance benchmark.

This 12-question retrieval-only Kestrel comparison is separate from Person B's
10-question generation-enabled redaction summary in this directory. Its scores
must not be compared directly without matching question subsets and settings.
Historical V2/V3 files and Person B's aggregate summary were not changed.

## Reproduction

From the repository root with dependencies installed, use the existing runner
for each configuration. Write individual runs to ignored temporary paths first:

```bash
python -m evaluation.rag_evaluation --dataset baking --retrievers dense --chunk-size 800 --overlap 80 --top-k 5 --output evaluation/results/runs/v4-baking-dense.jsonl
python -m evaluation.rag_evaluation --dataset baking --retrievers dense bm25 --chunk-size 800 --overlap 80 --top-k 5 --output evaluation/results/runs/v4-baking-dense-bm25.jsonl
python -m evaluation.rag_evaluation --dataset kestrel --retrievers dense --chunk-size 800 --overlap 80 --top-k 5 --output evaluation/results/runs/v4-kestrel-dense.jsonl
python -m evaluation.rag_evaluation --dataset kestrel --retrievers dense bm25 --chunk-size 800 --overlap 80 --top-k 5 --output evaluation/results/runs/v4-kestrel-dense-bm25.jsonl
python -m evaluation.rag_evaluation --dataset kestrel --retrievers dense bm25 graph --chunk-size 800 --overlap 80 --top-k 5 --output evaluation/results/runs/v4-kestrel-dense-bm25-graph.jsonl
```

Each command writes a raw JSONL file and a sibling `_summary.jsonl`. To reproduce
the bundles, concatenate raw files in the order above, and concatenate summary
files in the same order. Do not add `--generate-answers` for this comparison.
The committed comparison endpoints for V2 are unchanged; this report does not
silently replace the data those endpoints serve.
