# BakeFix

BakeFix is a retrieval-augmented generation (RAG) application for answering
questions from document collections. It combines a FastAPI backend with a
React/Vite frontend. Dense vector search is available for both the baking and
Kestrel datasets; BM25 and knowledge-graph retrieval can also be selected, with
graph retrieval limited to Kestrel. Retrieved passages are the evidence for
generated answers; graph paths provide navigation context and do not replace
source passages.

See [REPORT.md](REPORT.md) for design decisions, evaluation findings, and
limitations. The [Kestrel corpus guide](kestrel-kb/README.md) describes its
fictional documents and question set, and [design/UI-UX-PLAN.md](design/UI-UX-PLAN.md)
contains interface planning notes.

## Project map

| Path | Purpose |
| --- | --- |
| `backend/` | FastAPI routes, document/chunk handling, dense and BM25 retrieval, graph retrieval, generation, and API schemas. |
| `tests/` | Automated backend tests and manual retrieval smoke checks. |
| `frontend/` | React user interface for asking questions, managing documents, retrieval settings, evaluations, and word analytics. |
| `corpus/` | Baking source documents used by the application. |
| `docs/` | Additional source documents available to the document loader. |
| `kestrel-kb/` | Kestrel source documents, evaluation starter questions, graph data, and corpus guide. |
| `evaluation/` | Evaluation commands, question sets, metric code, committed results, and comparisons. |
| `design/` | UI and UX planning material. |
| `chroma_db/` | Local persistent Chroma storage created at runtime; ignored by Git. |

## Requirements and configuration

Use Python 3.10 or newer and Node.js with npm. Install the Python dependencies
from the repository root and create a local environment file:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Set `GOOGLE_API_KEY` in `.env` to enable answer generation and Gemini-backed
graph extraction. The backend uses Gemini through its OpenAI-compatible API;
`GEMINI_MODEL` is optional and defaults to `gemini-3.5-flash-lite`. Retrieval
embeddings use the local `all-MiniLM-L6-v2` Sentence Transformers model, which
may be downloaded on first use. The `.env` file contains a secret and should
remain local.

## Run locally

Start the API from the repository root:

```bash
python -m uvicorn backend.main:app --reload
```

In another terminal, start the frontend:

```bash
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite, usually `http://localhost:5173`. Its `/api`
requests are proxied to the backend on port 8000. The API's interactive
documentation is available at `http://localhost:8000/docs`; `GET /health`
provides a basic health check. Without a built frontend, `/` redirects to the
API documentation.

To build and serve the frontend through FastAPI:

```bash
cd frontend
npm install
npm run build
cd ..
python -m uvicorn backend.main:app
```

The production bundle is served from `http://localhost:8000/`. Generated
`frontend/dist/` output is ignored; source files and the package lockfile are
tracked.

## Features and API overview

- **Ask and evidence:** submit a question, choose dataset/documents and retrieval
  settings, and inspect the generated answer and cited passages. The backend
  validates response structure and citations and can abstain when evidence is
  insufficient.
- **Document library:** list, upload, and delete UTF-8 Markdown or plain-text
  files in `corpus/`; changes trigger index rebuilding. The loader also reads
  supported `.md` and `.txt` files already present in the corpus tree.
- **Retrievers:** Dense uses MiniLM embeddings and Chroma cosine distance;
  BM25 uses token-based sparse ranking; Graph follows extracted Kestrel
  relationships. Multiple selected retrievers are combined by reciprocal rank
  fusion. Graph uses its saved 800/80 chunk build and is Kestrel-only.
- **Path as Context:** optionally provide graph paths alongside retrieved
  supporting passages for Kestrel answer generation. Supporting document chunks
  remain the evidence used for answers and citations.
- **Evaluations:** run answer-generation evaluations from the UI or CLI, compare
  retrieval configurations, and inspect HitRate and evidence Recall at several
  cutoffs. Retrieval comparison endpoints serve committed experiment results.
- **Words analytics:** explore token counts across corpus documents and chunks,
  and inspect which chunks contain words from the fixed question sets.

The main API groups are document and settings routes, `/api/retrieve` and
`/api/ask`, `/api/evaluations`, `/api/evaluations/retrieval/...`, and
`/api/words...`. Browse `/docs` for request/response schemas and the complete
route list.

## Ask traces

Every `POST /api/ask` request receives a trace, including invalid requests,
abstentions, and failed generations. Successful Ask responses contain a
`trace_id`; error responses expose it in the `X-Trace-ID` header. Fetch the
trace with `GET /api/traces/{trace_id}`, or use the answer's **Details** button
in the UI.

Traces are stored in a local SQLite database at `.bakefix/traces.sqlite3` by
default. Set `BAKEFIX_TRACE_DB` to use another local path. Expired traces are
purged when a trace is created or fetched. Trace spans record step status,
duration, and safe
metadata such as model and token counts; they do not store prompts, document
text, or API keys. The Details endpoint has no authentication and is intended
for this local single-user app; do not expose the backend publicly.

## Documents, indexes, and graph data

The shared document loader reads UTF-8 `.md` and `.txt` files from `corpus/`.
The baking corpus contains the baking guides; the Kestrel corpus is under
`kestrel-kb/docs/`. The default dense index is persisted locally in `chroma_db/`.
Document uploads and deletions rebuild the application index; an empty index is
built on first query. Dense retrieval checks for changed corpus content and
settings and refreshes stale data. Local index state is disposable and can be
rebuilt from the source documents.

Kestrel graph data is committed under `kestrel-kb/graph/`. It contains the
extracted graph, entity-resolution rules, and a quality-review sample. Graph
retrieval expects the saved 800-character chunks with 80-character overlap;
requests using incompatible graph chunk settings are rejected. Graph creation
uses Gemini and is a separate extraction workflow; the committed graph can be
used for retrieval without re-running extraction. Review the Kestrel guide and
report before changing the evaluation corpus or question set.

## Evaluations

The CLI supports `baking` and `kestrel` datasets. For example:

```bash
python -m evaluation.rag_evaluation \
  --dataset baking \
  --top-k 5 \
  --chunk-size 800 \
  --overlap 80
```

Use `--dataset kestrel` for the Kestrel set. Optional `--max-distance` and
`--limit` arguments filter results or cap question count. CLI output is written
to `evaluation/results/<dataset>_rag.jsonl`. The UI starts runs through
`POST /api/evaluations`, polls `GET /api/evaluations/{run_id}`, then loads
`GET /api/evaluations/{run_id}/results`; API-run outputs are stored in unique
directories under `evaluation/results/runs/`. Run metadata is persisted, while
the job registry and per-dataset concurrency guard are in-process, so this
workflow expects one backend process.

The Evaluation tab supports Dense, BM25, Dense + BM25, Graph, Dense + Graph,
and Dense + BM25 + Graph, along with 800/80 and 400/40 chunking presets. Graph
configurations are Kestrel-only and use the saved graph chunking configuration.
Optional Path as Context comparison makes paired generation calls with the same
retrieved evidence; questions without graph paths have an unavailable context
arm. These generation calls use the configured provider.

Metrics include HitRate@k and macro evidence Recall@k overall and by question
type for k = 1, 3, 5, and 10. Evidence relevance requires an expected source and
complete expected quote in a retrieved passage, with whitespace normalized;
unanswerable questions have null per-question metrics and are excluded from
aggregates. Retrieval metrics describe evidence coverage, not generated-answer
correctness. Latencies are observed local wall-clock timings, not controlled
benchmarks; provider timings include network and model time.

The separate retrieval-comparison API reads committed result and summary files
for 800/80 and 400/40:

- `GET /api/evaluations/retrieval/retrieval-v2-baking/results`
- `GET /api/evaluations/retrieval/retrieval-v2-kestrel/results`

Raw results and discussion are in [evaluation/results/](evaluation/results/)
and [the V3 comparison](evaluation/results/v3/COMPARISON.md). See
[REPORT.md](REPORT.md) for methodology, interpretation, and known limitations.

## Words analytics

The Words view uses the same document loader and chunking implementation as
retrieval and evaluation. Chunk size and overlap default to 800/80 and can be
changed in the UI. Matching is case-insensitive and token-based; punctuation
separates tokens, so `KST-2044` is counted as `kst` and `2044`. Corpus totals
count source tokens once; overlapping chunks can make summed chunk counts
higher.

- `GET /api/words?dataset=baking&chunk_size=800&overlap=80` returns paginated
  vocabulary with source occurrence and distinct chunk counts.
- `GET /api/words/{word}/chunks?dataset=kestrel&chunk_size=800&overlap=80`
  returns matching chunks and per-chunk counts.
- `GET /api/words/questions?dataset=baking` returns the fixed dataset question
  set.
- `POST /api/words/analyze-question` accepts dataset, question, chunk size, and
  overlap, then returns found/missing words and matching chunks.

## Troubleshooting

- **Answer generation or graph extraction is unavailable:** check that `.env`
  contains a valid `GOOGLE_API_KEY`, then restart the backend.
- **First retrieval is slow or fails while loading embeddings:** ensure the
  machine can download the Sentence Transformers model and retry after the
  download completes.
- **The UI cannot reach the API:** run FastAPI on port 8000 and use the Vite URL
  printed by `npm run dev`; the development proxy targets that backend.
- **Graph retrieval rejects settings:** use Kestrel with chunk size 800 and
  overlap 80, matching the committed graph build.
- **An index seems stale or corrupted:** the Chroma directory is local generated
  state. Stop the backend, remove `chroma_db/`, then restart and let the index
  rebuild from source documents.

## Run tests

From the repository root, with your Python environment activated:

```bash
python -m unittest discover -s tests -t . -p 'test_*.py' -v
```

Tests use the local embedding model; download it once before running offline.
Generation calls in the automated suite are mocked and do not require a Gemini key.

For a manual retrieval smoke check (rebuilds the baking index):

```bash
python -m tests.retrieval_smoke_test
```
