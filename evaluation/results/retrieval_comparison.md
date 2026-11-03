# V2 retrieval configuration comparison

Both datasets used unchanged question sets, MiniLM embeddings, cosine distance, no distance threshold, and no answer generation. Metrics require the expected source and a complete supporting quote in one chunk (whitespace normalized). Recall is averaged per answerable question. Unanswerable questions are excluded.

| Corpus | Chunk size / overlap | Answerable | k | HitRate | Recall |
|---|---|---:|---:|---:|---:|
| baking | 800/80 | 10 | 1 | 50.0% | 17.5% |
| baking | 800/80 | 10 | 3 | 100.0% | 72.5% |
| baking | 800/80 | 10 | 5 | 100.0% | 79.2% |
| baking | 800/80 | 10 | 10 | 100.0% | 84.2% |
| baking | 400/40 | 10 | 1 | 10.0% | 3.3% |
| baking | 400/40 | 10 | 3 | 70.0% | 38.3% |
| baking | 400/40 | 10 | 5 | 70.0% | 44.2% |
| baking | 400/40 | 10 | 10 | 100.0% | 75.8% |
| kestrel | 800/80 | 8 | 1 | 62.5% | 40.6% |
| kestrel | 800/80 | 8 | 3 | 87.5% | 81.2% |
| kestrel | 800/80 | 8 | 5 | 87.5% | 81.2% |
| kestrel | 800/80 | 8 | 10 | 100.0% | 93.8% |
| kestrel | 400/40 | 8 | 1 | 25.0% | 12.5% |
| kestrel | 400/40 | 8 | 3 | 75.0% | 65.6% |
| kestrel | 400/40 | 8 | 5 | 75.0% | 71.9% |
| kestrel | 400/40 | 8 | 10 | 75.0% | 71.9% |

## Results by question type

| Corpus | Chunk size / overlap | Type | Answerable | k | HitRate | Recall |
|---|---|---|---:|---:|---:|---:|
| baking | 800/80 | other | 7 | 1 | 42.9% | 14.3% |
| baking | 800/80 | other | 7 | 3 | 100.0% | 69.0% |
| baking | 800/80 | other | 7 | 5 | 100.0% | 78.6% |
| baking | 800/80 | other | 7 | 10 | 100.0% | 85.7% |
| baking | 800/80 | split_answer | 3 | 1 | 66.7% | 25.0% |
| baking | 800/80 | split_answer | 3 | 3 | 100.0% | 80.6% |
| baking | 800/80 | split_answer | 3 | 5 | 100.0% | 80.6% |
| baking | 800/80 | split_answer | 3 | 10 | 100.0% | 80.6% |
| baking | 400/40 | other | 7 | 1 | 14.3% | 4.8% |
| baking | 400/40 | other | 7 | 3 | 57.1% | 28.6% |
| baking | 400/40 | other | 7 | 5 | 57.1% | 33.3% |
| baking | 400/40 | other | 7 | 10 | 100.0% | 69.0% |
| baking | 400/40 | split_answer | 3 | 1 | 0.0% | 0.0% |
| baking | 400/40 | split_answer | 3 | 3 | 100.0% | 61.1% |
| baking | 400/40 | split_answer | 3 | 5 | 100.0% | 69.4% |
| baking | 400/40 | split_answer | 3 | 10 | 100.0% | 91.7% |
| kestrel | 800/80 | exact_identifier | 2 | 1 | 50.0% | 25.0% |
| kestrel | 800/80 | exact_identifier | 2 | 3 | 50.0% | 50.0% |
| kestrel | 800/80 | exact_identifier | 2 | 5 | 50.0% | 50.0% |
| kestrel | 800/80 | exact_identifier | 2 | 10 | 100.0% | 100.0% |
| kestrel | 800/80 | split_answer | 2 | 1 | 100.0% | 62.5% |
| kestrel | 800/80 | split_answer | 2 | 3 | 100.0% | 100.0% |
| kestrel | 800/80 | split_answer | 2 | 5 | 100.0% | 100.0% |
| kestrel | 800/80 | split_answer | 2 | 10 | 100.0% | 100.0% |
| kestrel | 800/80 | two_hop | 1 | 1 | 100.0% | 50.0% |
| kestrel | 800/80 | two_hop | 1 | 3 | 100.0% | 50.0% |
| kestrel | 800/80 | two_hop | 1 | 5 | 100.0% | 50.0% |
| kestrel | 800/80 | two_hop | 1 | 10 | 100.0% | 50.0% |
| kestrel | 800/80 | versions | 2 | 1 | 0.0% | 0.0% |
| kestrel | 800/80 | versions | 2 | 3 | 100.0% | 100.0% |
| kestrel | 800/80 | versions | 2 | 5 | 100.0% | 100.0% |
| kestrel | 800/80 | versions | 2 | 10 | 100.0% | 100.0% |
| kestrel | 800/80 | vocabulary | 1 | 1 | 100.0% | 100.0% |
| kestrel | 800/80 | vocabulary | 1 | 3 | 100.0% | 100.0% |
| kestrel | 800/80 | vocabulary | 1 | 5 | 100.0% | 100.0% |
| kestrel | 800/80 | vocabulary | 1 | 10 | 100.0% | 100.0% |
| kestrel | 400/40 | exact_identifier | 2 | 1 | 50.0% | 25.0% |
| kestrel | 400/40 | exact_identifier | 2 | 3 | 50.0% | 50.0% |
| kestrel | 400/40 | exact_identifier | 2 | 5 | 50.0% | 50.0% |
| kestrel | 400/40 | exact_identifier | 2 | 10 | 50.0% | 50.0% |
| kestrel | 400/40 | split_answer | 2 | 1 | 0.0% | 0.0% |
| kestrel | 400/40 | split_answer | 2 | 3 | 100.0% | 62.5% |
| kestrel | 400/40 | split_answer | 2 | 5 | 100.0% | 87.5% |
| kestrel | 400/40 | split_answer | 2 | 10 | 100.0% | 87.5% |
| kestrel | 400/40 | two_hop | 1 | 1 | 0.0% | 0.0% |
| kestrel | 400/40 | two_hop | 1 | 3 | 0.0% | 0.0% |
| kestrel | 400/40 | two_hop | 1 | 5 | 0.0% | 0.0% |
| kestrel | 400/40 | two_hop | 1 | 10 | 0.0% | 0.0% |
| kestrel | 400/40 | versions | 2 | 1 | 0.0% | 0.0% |
| kestrel | 400/40 | versions | 2 | 3 | 100.0% | 100.0% |
| kestrel | 400/40 | versions | 2 | 5 | 100.0% | 100.0% |
| kestrel | 400/40 | versions | 2 | 10 | 100.0% | 100.0% |
| kestrel | 400/40 | vocabulary | 1 | 1 | 100.0% | 50.0% |
| kestrel | 400/40 | vocabulary | 1 | 3 | 100.0% | 100.0% |
| kestrel | 400/40 | vocabulary | 1 | 5 | 100.0% | 100.0% |
| kestrel | 400/40 | vocabulary | 1 | 10 | 100.0% | 100.0% |

## Findings

- Keep 800/80 as the measured baseline: 400/40 lowered HitRate@5 and Recall@5 on both datasets. This experiment did not improve retrieval.
- Kestrel q01: 800/80 recovers both expected quotes at rank 7, outside top 5. With 400/40 neither appears in the top 10.
- Kestrel q08: 800/80 recovers the runbook quote at rank 1 but not the catalog channel quote in the top 10. With 400/40 neither labeled quote appears in the top 10.
- Baking B07: both settings recover only 1/3 expected quotes even at k=10. HitRate alone hides incomplete evidence.
- With 400/40, four baking evidence quotes (B02 evidence 1, B03 evidence 1, B06 evidence 2, B07 evidence 1) cross chunk boundaries and cannot match as complete quotes. There are no such boundary cases at 800/80. This contributes to the recall decrease; it is distinct from ranking failures.
- Labels are the existing dataset quotes. Some quotes are short fragments; these scores measure labeled-quote recovery, not complete answer correctness. No generation or abstention quality is claimed.
- Measured Words Analytics observations for Kestrel and baking misses are recorded in [the miss diagnoses](retrieval_miss_diagnoses.md), using the merged Question Mode API and matching chunk settings.

## Reproduce

From the project root, with the virtual environment active:

```bash
for dataset in baking kestrel; do
  python -m evaluation.rag_evaluation --dataset "$dataset" --chunk-size 800 --overlap 80
  python -m evaluation.rag_evaluation --dataset "$dataset" --chunk-size 400 --overlap 40
done
```

These commands rebuild only the isolated evaluation indexes and overwrite the corresponding configuration result files. Original answer-generation result files are separate. Each run saves question results and a companion summary JSONL.
