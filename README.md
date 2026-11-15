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
| `docs/` | Supplementary material and presentation notes; not automatically loaded by the default corpus loader. |
| `kestrel-kb/` | Kestrel source documents, evaluation starter questions, graph data, and corpus guide. |
| `evaluation/` | Evaluation commands, question sets, metric code, committed results, and comparisons. |
| `design/` | UI and UX planning material. |
| `chroma_db/` | Local persistent Chroma storage created at runtime; ignored by Git. |

## Requirements and configuration

Python 3.12 is the verified environment (the application uses Python 3.10+
syntax). Use Node.js 22.12+ or Node 20.x at least 20.19, as required by the
installed Vite version; verification used Node 24.10.0. Python requirements are
not fully pinned, so these checks are not a guarantee for every future resolver
combination.

From the repository root, install dependencies and create a local environment file:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m spacy download en_core_web_sm
cp .env.example .env
```

Set `GOOGLE_API_KEY` in `.env` to enable answer generation and Gemini-backed
graph extraction. The backend uses Gemini through its OpenAI-compatible API;
`GEMINI_MODEL` is optional and defaults to `gemini-3.5-flash-lite`. Retrieval
embeddings use the local `all-MiniLM-L6-v2` Sentence Transformers model, which
may be downloaded on first use. The `.env` file contains a secret and should
remain local. Set the key only in your local file; do not commit it. The
spaCy English model above is required for Presidio redaction. Explicitly
installing it avoids a download during the first redaction request.

To cache the local embedding model before offline use:

```bash
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

Backend imports initialize this embedder, so first startup can require network
access. After caching, `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1` enables offline
model loading; Gemini generation still requires network access. No hosted
embedding API is used.

## Run locally

Start the API from the repository root:

```bash
python -m uvicorn backend.main:app --reload
```

In another terminal, start the frontend:

```bash
cd frontend
npm ci
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
npm ci
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
  files in `corpus/`; new uploads are validated/scanned before corpus writes.
  Unflagged files are indexed; suspicious files go to quarantine. The loader also
  reads supported files already present in the corpus tree. PDF/DOCX extraction
  is not implemented.
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
duration, and safe metadata such as model and token counts; they do not store prompts, document
text, or API keys. The Details endpoint has no authentication and is intended
for this local single-user app; do not expose the backend publicly.

Upload/delete/settings operations also use this recorder. Indexing dictionary
results contain `trace_id`, and indexing HTTP responses carry `X-Trace-ID`.
Stages include `load_documents`, `chunking`, `embedding_indexing`, and optional
`graph_extraction`; scanner/review operations add their own spans. A stale rebuild
during Ask shares the question trace. Standalone rebuilds create an indexing
trace. Traces expire after 30 days; documents and findings are not trace payloads.
The shared Details component is connected to Ask responses, indexing activity,
review actions and concept neighbourhoods. Browsing the concept list does not
create a trace; opening a concept does.

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

Explicit Dense indexing commands (these change local disposable index state):

```bash
python -c "from backend.retrieval import rebuild_index; print(rebuild_index(chunk_size=800, overlap=80, dataset='baking'))"
python -c "from backend.retrieval import rebuild_index; print(rebuild_index(chunk_size=800, overlap=80, dataset='kestrel'))"
```

Manual rebuild arguments do not save UI settings. Select 800/80 in the settings
interface before using Graph. Ordinary indexing does not rebuild the graph.
Only when deliberately regenerating it, with a configured Gemini key, use:

```bash
python -c "from backend.graph_index import build_kestrel_graph; build_kestrel_graph(chunk_size=800, overlap=80)"
```

That command makes provider calls and overwrites the saved graph. Loading the
committed graph requires no extraction call. New Kestrel documents are available
to Dense/BM25 after indexing; Graph needs a separate reviewed extraction update.

## Concept Map and original sources

Select **Kestrel** in the Ask interface to open the concept explorer. Search or
select a concept, follow a relationship, expand its supporting passage and open
the original document. The graph requires matching 800/80 settings.

Available endpoints:

- `GET /api/concepts?query=postroom` returns `{ "concepts": [...] }`.
- `GET /api/concepts/{id}` returns the concept, neighbours and `trace_id`.
- `GET /api/chunks/{id}?dataset=kestrel&graph_evidence=true` checks graph settings
  and the original supporting quote before returning evidence.
- `GET /api/document-text?document_id=service-catalog.md&dataset=kestrel`
  returns original text from the selected corpus.

Concepts contain `id`, `name` and `type`. Neighbours preserve uppercase relation
labels, incoming/outgoing direction and supporting `chunk_ids`. The explorer
reuses V3 aliases and review exclusions, keeping same-name/different-type
entities distinct. V3 has no stored entity IDs, so IDs are derived from typed
names. Regular chunk requests default to Baking unless a dataset is supplied.
Original document access rejects traversal, unsupported extensions and escaping
symlinks. Missing concepts/documents return 404; unavailable graph settings
return `GRAPH_UNAVAILABLE` (409) on concept routes.

Backend helpers are also available:

```python
from backend.concept_map import list_concepts, get_concept_neighbourhood

concepts = list_concepts("postroom")
if concepts:
    detail = get_concept_neighbourhood(concepts[0].id).model_dump()
```

The route schemas accept these Pydantic models; a duplicate service or renaming
adapter is not required for the integrated interface. The implemented prefix is
`/api/concepts`, superseding the earlier proposed `/api/graph/concepts` prefix.

## Upload scanning and quarantine review

`POST /api/documents` accepts UTF-8 `.md`/`.txt` files into Baking. Its response
preserves `filename` and adds `status` (`indexed` or `quarantined`), `findings` and
`trace_id`. Quarantined results include `quarantine_id`; indexed results include
index statistics. Suspicious documents are stored as UUID-named JSON records
under `.bakefix/quarantine/`, outside all indexed roots and ignored by Git.
They remain absent from normal browsing, Dense, BM25 and graph inputs.

Review services are available from `backend.quarantine`:

```python
from backend.quarantine import (
    list_quarantined_documents, get_quarantined_document,
    release_quarantined_document, reject_quarantined_document,
)

items = list_quarantined_documents()
# Inspect an actual item using get_quarantined_document(items[0]["id"]).
# Only after review, choose ONE action with its actual ID:
# release_quarantined_document("QUARANTINE_ID", approved=True)
# reject_quarantined_document("QUARANTINE_ID")
```

Release revalidates the destination and uses saved chunk settings unless
explicitly overridden. Rejection drops the document payload. A `releasing` item
is an approved operation interrupted by a failure: retry explicit release after
resolving the error. It is not a successful release. Atomic records and file locks
protect transitions; they do not make Chroma and filesystem writes transactional.

The Baking document library shows flagged uploads under **Held for review**.
Inspect findings and explicitly confirm review to release an item, or reject it.

- `GET /api/quarantine` returns `{ "items": [...] }` without raw payloads.
- `POST /api/quarantine/{id}/release` requires JSON `{ "approved": true }`.
- `POST /api/quarantine/{id}/reject` discards a held payload.

Review results expose a trace ID, also available in `X-Trace-ID`. Missing IDs
return 404, invalid IDs/approval return 422, and repeated actions or filename
conflicts return 409. Upload feedback distinguishes `indexed` and `quarantined`.
Findings are untrusted review text and are excluded from traces.

The low-level `backend.injection_scanner.scan_document(text)` returns findings;
`add_document_and_reindex(...)` supplies validation, storage, status and shared
trace handling. The integrated upload route calls this wrapper before any
corpus write. Do not call the private publish helper directly from an upload route.

The scanner is deterministic screening, not a complete security boundary. Its
20-case evaluation contains both false positives and false negatives:

```bash
python -m evaluation.injection_evaluation
```

## Answer style controls and glossary

Use the Ask style controls for level (`beginner`/`expert`), tone
(`friendly`/`professional`/`technical`), length (`short`/`medium`/`long`) and ELI12.
The frontend remembers preferences locally and sends optional `style` to
`POST /api/ask`. Defaults keep older requests valid.

Responses can contain `glossary` entries with `term`, `definition` and
`chunk_id`. Supporting IDs must be retrieved and cited, though ID checks alone
do not establish definition correctness. The UI displays the glossary with
source navigation. Traces record provider token usage when supplied and estimated
`cost_usd` through the configured pricing helper; missing usage/unknown rates do
not create invented costs.

Current privacy scope: full Presidio redaction applies to questions; retrieved
text and graph context receive conservative email/phone filtering. This
preserves document product/team names and q01's technical identifiers/IPs, but
not every person name or secret embedded in documents. Local mock-provider
checks confirmed synthetic document names/keys can remain, and technical names
in questions can still be falsely redacted. Person B must review that policy
before broader privacy guarantees are made.

## Evaluations

The CLI supports `baking` and `kestrel` datasets. For example:

```bash
python -m evaluation.rag_evaluation \
  --dataset baking \
  --top-k 5 \
  --chunk-size 800 \
  --overlap 80 \
  --retrievers dense \
  --output evaluation/results/runs/manual-baking-dense-800-80.jsonl
```

Use `--dataset kestrel` for the Kestrel set. Optional `--max-distance` and
`--limit` arguments filter results or cap question count. CLI output is written
to the explicit path above, with a sibling `_summary.jsonl` file. Without
`--output`, names encode dataset, retrieval/generation mode, chunk settings and
applicable options. Generation is opt-in with `--generate-answers`; it makes
provider calls. The UI starts runs through
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

The [V4 release comparison](evaluation/results/v4/RETRIEVAL_COMPARISON.md)
contains five rerun configurations at 800/80, top-k=5, no distance threshold and
unchanged MiniLM/question sets. All-k and per-type results match V3. Two JSONL
bundles retain 60 per-question records and five summaries. These retrieval-only
results are separate from 10-question generation/redaction summary.
Historical V2/V3 files remain unchanged; final team approval of the submitted
configuration is still required.

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
- **Presidio cannot initialize:** run `python -m spacy download en_core_web_sm`
  in the same environment as FastAPI; allow local cache access for its dependencies.
- **`react-markdown` cannot be resolved:** run `npm ci` in `frontend/` before
  typechecking/building.
- **A concept URL returns 404:** use `/api/concepts`, not the earlier proposed
  `/api/graph/concepts`. For original documents use `/api/document-text`.
- **The concept map is unavailable:** set Search options to 800/80; changed or
  missing supporting evidence requires a deliberately reviewed graph update.
- **A `style` request returns 422:** use accepted level/tone/length values and
  boolean `eli12`; inspect `/docs` for the current schema.
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

Frontend regression checks, from the repository root:

```bash
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

Final verification used `backend/.venv/bin/python`; an activated fresh environment
uses the same commands with `python`. Tests use isolated corpus/index fixtures;
manual indexing/smoke commands deliberately rebuild local application indexes.