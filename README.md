# BakeFix

BakeFix is a small RAG application with a React frontend and a FastAPI backend.

## Backend setup

Install the Python dependencies from the repository root and provide a Google
Gemini API key in `.env`:

```bash
python -m pip install -r requirements.txt
```

```dotenv
GOOGLE_API_KEY=your_google_api_key
```

The backend indexes `.txt` and `.md` files in `docs/`, uses the local
`all-MiniLM-L6-v2` embedding model with Chroma cosine distance, and persists the
vector index locally in `chroma_db/`. The first index or query may download the
embedding model. Add documents through the API or place source documents in
`docs/`; the index is rebuilt after uploads and on the first query when empty.

## Frontend development

The frontend lives in `frontend/` and uses React with Vite. Start the API and
the frontend development server in separate terminals:

```bash
# Terminal 1 — from the repository root
python -m uvicorn backend.main:app --reload

# Terminal 2
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite (usually `http://localhost:5173`). Requests to
`/api` are proxied to the FastAPI server on port 8000.

## Production frontend

Build the static frontend bundle, then run FastAPI from the repository root:

```bash
cd frontend
npm install
npm run build
cd ..
python -m uvicorn backend.main:app
```

The built frontend is served from FastAPI at `http://localhost:8000/`. The
generated `frontend/dist/` directory is ignored by Git; commit the frontend
source and package lockfile instead.

## V2 evaluations

The evaluation runner supports the `baking` and `kestrel` datasets. From the
repository root, run an evaluation with:

```bash
python -m evaluation.rag_evaluation \
  --dataset baking \
  --top-k 5 \
  --chunk-size 800 \
  --overlap 80
```

Use `--dataset kestrel` to evaluate the Kestrel knowledge base. Optional
`--max-distance` and `--limit` arguments filter retrieved chunks or limit the
number of questions. CLI runs write their JSONL results to
`evaluation/results/<dataset>_rag.jsonl`.

The frontend Evaluation tab starts a run through `POST /api/evaluations`,
checks progress with `GET /api/evaluations/{run_id}`, and loads completed
results with `GET /api/evaluations/{run_id}/results`. API-started runs write to
unique directories under `evaluation/results/runs/`, so they do not overwrite
the CLI result files. Run metadata is persisted, but the job registry and
per-dataset concurrency guard are in-process; use one backend process for this
local V2 workflow.

The Evaluation tab also exposes the V3 retriever configurations (Dense, BM25,
Dense + BM25, Graph, Dense + Graph, and Dense + BM25 + Graph), the `800/80`
and `400/40` chunking presets, and a Graph-only Path as Context comparison
option. Graph configurations are restricted to Kestrel. Run results display
HitRate@k and macro evidence Recall@k overall and by question type for
k = 1, 3, 5, and 10. Dense, BM25, and Graph adapters are available; Graph is
Kestrel-only. Optional Path as Context comparison makes paired answer-generation
calls using the same retrieved evidence, and marks questions with no graph paths
as unavailable for that comparison. These provider calls are opt-in.

Each result records per-adapter wall-clock latency, total retrieval/orchestration
latency, and generation latency for each comparison arm. The summary JSONL
reports the mean and median in milliseconds. These are local observed timings,
not controlled benchmark results; provider latency includes network/model time.

Run the evaluation run-service checks with:

```bash
python -m unittest backend.test_evaluation_runs
```

The measured retrieval-only comparison is exposed separately from those
answer-generation runs. It reads the committed, precomputed result and summary
JSONL files for the `800/80` and `400/40` configurations:

- `GET /api/evaluations/retrieval/retrieval-v2-baking/results`
- `GET /api/evaluations/retrieval/retrieval-v2-kestrel/results`

The response contains the aggregate HitRate and evidence Recall at k = 1, 3, 5,
and 10, question-type breakdowns, and per-question evidence and retrieved
passages. Passage rank follows the `evaluation_chunks` array order; passages
are labeled relevant when they contain an expected source and complete quote
(whitespace normalized). Unanswerable questions keep null per-question
metrics and are excluded from aggregate metrics. Recall is macro-averaged per
answerable question. This endpoint reports retrieval evidence coverage only;
it does not claim answer-generation quality.

Run the retrieval comparison API checks with:

```bash
python -m unittest backend.test_retrieval_comparison
```

## Words analytics API

The Words tab reads the `baking` and `kestrel` corpora using the shared
document loader and `chunk_text()` implementation. Chunk size and overlap
default to `800/80` and can be changed in the Words view to compare another
chunking setup, such as `400/40`. Chunk IDs use the same helper as retrieval
and evaluation.

Word matching is case-insensitive and token-based; punctuation separates
tokens, so `KST-2044` is analyzed as `kst` and `2044`. Corpus occurrence totals
count each token in the source documents once. Per-chunk counts reflect the
selected overlapping chunks, so adding per-chunk counts can exceed the
source-document total.

- `GET /api/words?dataset=baking&chunk_size=800&overlap=80` returns paginated
  vocabulary with source occurrence and distinct chunk counts.
- `GET /api/words/{word}/chunks?dataset=kestrel&chunk_size=800&overlap=80`
  returns matching chunks and per-chunk counts.
- `GET /api/words/questions?dataset=baking` returns the fixed question set for
  that dataset.
- `POST /api/words/analyze-question` accepts `dataset`, `question`,
  `chunk_size`, and `overlap`, then returns words found, missing words, and
  matching chunks.

The Words analytics checks can be run with:

```bash
python -m unittest backend.test_words_analytics
```
