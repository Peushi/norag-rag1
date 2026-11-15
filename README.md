# BakeFix

BakeFix answers kitchen questions from your own documents: recipes, baking
notes, and appliance manuals. Every answer shows the passages it came from,
and when your documents don't cover a question, BakeFix says so instead of
guessing. A fictional software company's help documents (Kestrel Analytics)
are included as a larger sample, with a Concept Map of how its services,
teams, and error codes connect.

## Using BakeFix

1. **Add documents** in "Your documents": drag a text (`.txt`) or Markdown
   (`.md`) file onto the box, or choose one; up to 1 MB. Files that look like they contain instructions aimed at
   the assistant are held for review instead of being added; open them under
   "Held for review" and decide.
2. **Ask a question**, or pick one of the examples. "Answer style" sets the
   reading level, tone, and length, or "Explain it like I'm 12".
3. **Read the answer and its sources.** Numbered sources show the exact
   passages used; "Words to know" explains specialist terms, and its `[2]`
   highlights the source it came from. "Copy answer" copies the answer with
   its sources; "Was this helpful?" keeps your rating in this browser only.
4. **See how it was made:** "Show the steps behind this answer" opens the
   trace (what was searched, what was found, model, tokens, and cost).
5. **Try the Kestrel sample** from "Search in" to explore the Concept Map and
   ask about a concept.

Retrieval settings live under "Search options"; developer tools (word
analytics and evaluation runs) are under "Behind the answers" in the header.

## How it works

BakeFix is a retrieval-augmented generation (RAG) application. It combines a FastAPI backend with a
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
| `aibom/` | AI bill of materials (CycloneDX), vulnerability decisions, and the VEX file. See [AI-BOM](#ai-bom-ai-bill-of-materials). |
| `scripts/` | AI-BOM generator and vulnerability scan. |
| `chroma_db/` | Local persistent Chroma storage created at runtime; ignored by Git. |
| `.bakefix/` | Local traces and documents held for review, created at runtime; ignored by Git. |

## Requirements and configuration

Python 3.12 is the verified environment (the application uses Python 3.10+
syntax). Use Node.js 22.12+ or Node 20.x at least 20.19, as required by the
installed Vite version; verification used Node 24.10.0. `requirements.txt`
sets compatible ranges; `requirements.lock.txt` pins the exact versions that
were tested (see below).

From the repository root, install dependencies and create a local environment file:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m spacy download en_core_web_sm
cp .env.example .env
```

Set `LLM_URL`, `LLM_API_KEY` and `LLM_MODEL` in `.env` (or `.env.local`, which
takes precedence) to enable answers and concept-graph extraction. BakeFix works
with **any OpenAI-compatible chat-completions API**; Google Gemini is only the
default:

| LLM | `LLM_URL` | `LLM_API_KEY` | `LLM_MODEL` (example) |
| --- | --- | --- | --- |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` | your key | `gemini-3.5-flash-lite` |
| OpenAI | `https://api.openai.com/v1` | your key | `gpt-4.1-mini` |
| Local Ollama | `http://localhost:11434/v1` | leave empty | `gpt-oss:20b` |

Verified with Gemini and with a local Ollama `gpt-oss:20b` (no key). For a
server that does not support JSON mode, BakeFix asks for JSON through the
prompt instead, and it accepts JSON wrapped in Markdown fences. Older `.env`
files with `GOOGLE_API_KEY` / `GEMINI_MODEL` still work. Retrieval
embeddings use the local `all-MiniLM-L6-v2` Sentence Transformers model, which
may be downloaded on first use. The `.env` file contains a secret and should
remain local. Set the key only in your local file; do not commit it. The
spaCy English model above is required for Presidio redaction. Explicitly
installing it avoids a download during the first redaction request.

To cache the local embedding model before offline use:

```bash
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2', revision='1110a243fdf4706b3f48f1d95db1a4f5529b4d41')"
```

The model is pinned to that Hugging Face commit in `backend/vector_store.py`,
so embeddings and evaluation results cannot change if the model is updated on
the Hub. To install the exact package versions BakeFix was tested with (macOS, Python 3.12), use
`python -m pip install -r requirements.lock.txt` instead of `requirements.txt`.

Backend imports initialize this embedder, so first startup can require network
access. After caching, `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1` enables offline
model loading; Gemini generation still requires network access. No hosted
embedding API is used.

> **If the backend hangs at startup with no output**, it is usually waiting
> on huggingface.co. Once the model is cached, start it offline:
> `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python -m uvicorn backend.main:app`

### Settings

| Variable | Default | Purpose |
| --- | --- | --- |
| `LLM_URL` | Google Gemini's OpenAI-compatible URL | Base URL of any OpenAI-compatible API. |
| `LLM_API_KEY` | (none) | API key; may be empty for local servers. Keep it in `.env`/`.env.local` only. |
| `LLM_MODEL` | `gemini-3.5-flash-lite` | Model name as the server knows it. |
| `LLM_TIMEOUT_SECONDS` | `60` | Time limit per LLM call (one retry); raise it for slow local models. |
| `BAKEFIX_TRACE_DB` | `.bakefix/traces.sqlite3` | Where traces are stored. |
| `BAKEFIX_ALLOWED_ORIGINS` | (none) | Extra comma-separated origins allowed to change data, if the UI is served from somewhere other than localhost. |
| `HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE` | unset | Set to `1` to load the cached embedding model without network access. |

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
trace with `GET /api/traces/{trace_id}`, or use **Show the steps behind this
answer** in the UI (other messages use a **Details** button).

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

Both corpora have a concept explorer: search or select a concept, follow a
relationship, expand its supporting passage and open the original document.

- **Kestrel sample:** uses its committed, manually reviewed graph (800/80).
- **My documents:** build the graph yourself. Upload documents, then press
  **Build the concept map** in the Concept map panel (under your documents).
  BakeFix sends each passage to the configured LLM once and extracts links
  between dishes, ingredients, equipment, techniques, problems and conditions
  (e.g. *cold oven → causes → pale, flat biscuits*), each with its exact quote.
  - **Incremental:** after uploading, changing or removing documents the panel
    says what is out of date; **Update the map** reads only new or changed
    documents (one LLM call per passage) and drops links from removed ones.
  - **Bounded:** at most 150 LLM calls per build; the rest can be added with
    another update. The panel shows the expected number of calls before you start.
  - **Use in search:** once built, **Concept graph** (and Path as Context) can be
    selected under Search options for your documents. Graph matching accepts
    word forms ("cookies keep spreading" finds *cookies spreading*).
  - The graph is stored locally in `.bakefix/graphs/baking/graph.json` (not in
    Git). Each build is an indexing trace (open it with "Details of the last build").
  - With a local LLM, extraction is slower (about 40 s per passage for
    `gpt-oss:20b` on a laptop): test with a few small documents first.
  - Extraction by a small model is useful but imperfect (e.g. it can miss a
    negation such as "little or no baking powder"); every link shows its quote
    so it can be checked.

Available endpoints (`dataset` is `kestrel` by default, or `baking`):

- `GET /api/concepts?query=postroom&dataset=kestrel` returns `{ "concepts": [...] }`;
  for an unbuilt graph it returns 409 `GRAPH_NOT_BUILT`.
- `GET /api/concepts/{id}?dataset=…` returns the concept, neighbours and `trace_id`.
- `GET /api/graphs/baking/status` reports whether the graph is built, up to
  date, being built (with progress), and how many LLM calls an update needs.
- `POST /api/graphs/baking/build` starts an incremental build (202 with
  `trace_id`; 409 if one is running; 503 if no LLM is configured). The Kestrel
  graph cannot be rebuilt from the app.
- `GET /api/chunks/{id}?dataset=…&graph_evidence=true` checks graph settings
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

## Security and privacy

BakeFix is a local, single-user app: the backend listens on `127.0.0.1` and
has no login, so do not expose it on a network. The main threat it defends
against is a document containing instructions aimed at the model. Each layer
assumes the one before it can fail:

1. **Upload checks:** `.md`/`.txt` only, safe file name, UTF-8, at most 1 MB.
2. **Injection scanner and review:** suspicious uploads are held in
   `.bakefix/quarantine/` (outside every corpus) until you approve them.
3. **Prompt framing:** passages and the question are wrapped in tags that
   document text cannot fake; the model is told that text inside them is data,
   and never to pass on requests to log in, reset an account, or visit a site.
4. **Output checks:** every cited passage must have been retrieved, or the
   answer is not shown.
5. **Safe display:** answers never load images, and links are shown as text.
6. **Request limits:** questions up to 2,000 characters, at most 4,096 output
   tokens per answer, 30-second timeout.
7. **Cross-site check:** requests that change data are refused (403) when
   another website's page sends them.

**What leaves your machine:** to write an answer, the question (with personal
data removed by Presidio) and the retrieved passages (with emails and phone
numbers removed) are sent to the configured LLM API (Google Gemini by default;
nothing leaves the machine if `LLM_URL` points to a local server). Other personal data inside
your documents is not removed, so do not upload documents you would not share
with Google. Traces stay local, contain no document text or questions, and
expire after 30 days.

The layers are tested end to end against real Gemini in
`python -m evaluation.defence_evaluation` (5 attacks, 3 runs each; results in
`evaluation/results/v4/`), and the scanner alone in
`python -m evaluation.injection_evaluation`.

## AI-BOM (AI bill of materials)

`aibom/bakefix.cdx.json` lists every model, dataset, and external AI service
BakeFix depends on, plus all pinned Python and npm packages, in the
[CycloneDX 1.6](https://cyclonedx.org/capabilities/mlbom/) format:

| Component | Type | Pinned by | Data leaves the machine? |
|---|---|---|---|
| `all-MiniLM-L6-v2` (embeddings) | model, with model card | Hugging Face commit + SHA-256 of the weights | No |
| `en_core_web_sm` (personal-data detection for Presidio) | model, with model card | wheel version + SHA-256 in `requirements.lock.txt` | No |
| Gemini API (answers; built the Kestrel graph) | external service + model card | default model name in `backend/llm_service.py` | **Yes:** the redacted question and retrieved passages |
| Baking corpus, Kestrel KB, Kestrel graph, evaluation sets | datasets | SHA-256 of the git-tracked files | No |

Each of the three model cards records the model's training data (as published),
limits, trade-offs, who could be served worse by it, and results measured on
our own evaluation sets: MiniLM's retrieval hit rate and recall, and Gemini's
manually graded answers (12/12 baking, 7/10 Kestrel). spaCy's card uses the
published OntoNotes scores and says so. Documents uploaded at runtime are not part of the
BOM. Gemini is pinned by name only: Google can update the model behind a name.

The BOM is generated, not written by hand. Descriptions, licences, and model
cards live in `aibom/ai-components.json`; versions, revisions, and hashes are
read from the code, the lock files, and the files themselves.

```bash
python scripts/generate_aibom.py                     # regenerate after a change
python -m pip install -r requirements-dev.txt        # once, for schema validation
python scripts/generate_aibom.py --check --validate  # up to date + valid CycloneDX
```

### Known vulnerabilities (VEX)

```bash
python scripts/scan_vulnerabilities.py   # needs network; pip-audit + npm audit
```

This checks every pinned package against the public advisory databases and
writes `aibom/bakefix.vex.cdx.json`: each finding with our decision from
`aibom/vulnerability-triage.json` (CycloneDX VEX states: `not_affected` with
the reason, or `resolved` by upgrading). It exits 1 if a finding has no
decision yet. Last scan (15 Nov 2026): no npm findings; 6 Python findings,
of which 2 were fixed by upgrading `oauthlib` and the OpenTelemetry packages,
and 4 are in Chroma's HTTP server, which BakeFix never runs (it embeds Chroma).

`tests/test_aibom.py` fails if the BOM no longer matches the code (for example,
after changing the model revision, updating a package, or editing a bundled
document) or if the cached model weights do not match the recorded hash.

## Troubleshooting

- **Answer generation or graph extraction is unavailable:** check `LLM_URL`,
  `LLM_API_KEY` and `LLM_MODEL` in `.env` or `.env.local`, then restart the
  backend. For a local server, check that it is running (e.g. `ollama serve`)
  and that the model is pulled.
- **A local model times out:** raise `LLM_TIMEOUT_SECONDS` (e.g. `300`).
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
- **The app says "BakeFix can't reach its server":** the backend is not
  running or not on port 8000; start it (see the startup-hang note above).
- **Changes are refused with `FORBIDDEN_ORIGIN` (403):** the UI is served from
  a host other than localhost; add it to `BAKEFIX_ALLOWED_ORIGINS`.
- **"The answer service returned an error" during many quick questions:**
  Gemini's free tier limits requests per minute (HTTP 429); wait a minute.
- **An index seems stale or corrupted:** the Chroma directory is local generated
  state. Stop the backend, remove `chroma_db/`, then restart and let the index
  rebuild from source documents.

## Run tests

From the repository root, with your Python environment activated:

```bash
python -m unittest discover -s tests -t . -p 'test_*.py' -v
```

Tests use the local embedding model; download it once before running offline.
Generation calls in the automated suite are mocked and do not require an LLM.

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