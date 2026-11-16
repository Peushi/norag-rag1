# Baking: graph retrieval evaluation (V4)

Graph retrieval on the Baking corpus became possible when users could build a
concept graph from their own documents. This run measures it with the same
method and labels as every other retrieval result.

## Setup

| | |
| --- | --- |
| Questions | `evaluation/baking_questions.jsonl`: 12 questions, 10 answerable, 2 not in the corpus (excluded from metrics) |
| Labels | The existing evidence labels (expected source + exact quote); no new labels were needed |
| Corpus | The 10 bundled guides in `corpus/` |
| Chunks | 800 characters, 80 overlap |
| Top-k | 5 (metrics also at 1, 3, 10) |
| Graph | `evaluation/graphs/baking/graph.json`: built once with Gemini (`gemini-3.5-flash-lite`) from the 10 guides; 144 relationships, 0 failed passages, 92 LLM calls including retries of rate-limited passages. Committed so the run is reproducible; not reviewed by hand |
| Generation | Off (retrieval only, no LLM calls at query time) |

Reproduce:

```bash
python -m evaluation.rag_evaluation --dataset baking --top-k 5 --chunk-size 800 --overlap 80 \
  --retrievers dense bm25 graph --output evaluation/results/v4/baking_dense_bm25_graph_800_80_graph_eval.jsonl
```

## Results (10 answerable questions)

| Method | Hit@1 | Recall@1 | Recall@3 | Recall@5 | Recall@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Dense | 50% | 17.5% | 72.5% | 79.2% | 84.2% |
| Dense + BM25 | 70% | 29.2% | 53.3% | 72.5% | 90.8% |
| Dense + BM25 + Graph | 20% | 10.0% | 51.7% | 77.5% | 90.8% |

Dense and Dense + BM25 match the V3/V4 results exactly, so only the graph changed.

## What it shows

- **Where the graph helps:** B03 ("brownies that are dense and moist rather
  than light") names a relationship the graph holds; it retrieved both evidence
  passages and Recall@5 rose from 50% to 100%. Overall, Recall@5 recovers 5 of
  the 6.7 points that BM25 cost.
- **Where it hurts:** for 8 of 10 questions the graph's top 5 passages contain
  no evidence. Kitchen concepts are everyday words ("dough", "cookies",
  "bread", "flour"), so many concepts match a question loosely and the graph
  returns related but unhelpful passages. Reciprocal rank fusion gives the
  graph's first result as much weight as Dense's or BM25's, so these passages
  often take rank 1: Hit@1 falls from 70% to 20%.
- **Contrast with Kestrel:** there concepts are specific identifiers
  ("KST-5031", "postroom") and Dense + BM25 + Graph had the best Recall@5
  (87.5%). A graph helps most when questions name specific things.

## Limits and next steps

- 10 answerable questions: one question moves Recall by about 10 points.
- The graph was extracted by a small model and not reviewed (Kestrel's was).
- Not tuned on these questions, to avoid fitting the test set. Candidates to
  evaluate on new questions: a lower fusion weight for the graph, matching only
  specific (multi-word or rarer) concepts, or adding relationship questions
  like Kestrel's two-hop set.
- In the app, "Concept graph" stays off by default for "My documents"; the
  user turns it on in Search options.
