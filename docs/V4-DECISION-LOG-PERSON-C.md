# V4 Decision Log — Person C (Sasha)

Working notes for my V4 section of `REPORT.md`: API, frontend, traces, and
feature integration. Each entry states the decision, the reason, and what I
rejected. To be rewritten in my own words for the report.

## Observability (Part A)

### Trace storage
- **Decision:** traces are stored in a local SQLite file
  (`.bakefix/traces.sqlite3`, configurable with `BAKEFIX_TRACE_DB`), one row
  per trace with its spans. Traces expire after 30 days; expired traces are
  purged when a trace is created or opened.
- **Why:** the app is local and single-user; SQLite needs no extra service and
  keeps traces on the machine.
- **Who can read them / do they leave the machine:** anyone with access to the
  local backend (`GET /api/traces/{id}` has no authentication); traces never
  leave the machine. The backend must not be exposed publicly.
- **Rejected:** JSON-lines files (harder to update a running trace and to
  purge); Langfuse/Phoenix (an extra service to install, and a hosted tool
  would send traces off the machine).

### What a question trace records
- **Decision:** one trace per `POST /api/ask`, including invalid requests and
  failures. The retrieval span records the settings (dataset, retrievers,
  top_k, chunk size, overlap, relevance threshold, whether a document filter
  was used and how many documents were selected) and, for each ranked
  passage, its chunk ID, source file name, position, fused score, and which
  retrievers found it at which rank (e.g. `dense#2; bm25#1`). Generation spans
  (Person B) add model, tokens, cost, and citation/glossary checks.
- **Never recorded:** the question, the prompt, chunk or document text, or
  API keys. Selected documents are recorded as a count, not as names.
- **Why:** this is enough to explain a wrong answer from the trace alone
  ("the right passage was ranked 7th") without storing personal data.
- **Personal-data trade-off:** I keep the source file name in each result
  because it makes the trace readable at a glance. File names are chosen by
  the user and could contain a name; the alternative was chunk IDs only.

### Indexing traces
- **Decision:** every change that rebuilds the index (upload, removal,
  settings change) creates an `indexing` trace (Person A adds the spans: load,
  chunking, embedding, injection scanning, quarantine). The user opens it
  from the message that describes that change ("… is ready to search",
  "… was held for review", "… was removed"). A stale-index rebuild triggered
  during a question is recorded as spans inside that question's trace.
- **Rejected:** a separate trace for the stale rebuild (the user would never
  see it next to the answer it delayed).

### Details view
- **Decision:** one shared "Details" component for answers, errors, uploads,
  removals, and settings. It shows the trace type, status, outcome, each span
  with its duration, and groups the per-passage attributes into a ranked
  "Retrieved passages" list. Decimals are rounded for display.
- **Why:** the same view everywhere; the demo is "ask, open Details, explain".

## User experience clean-up

### Audience
- **Decision:** BakeFix is for home cooks: recipes, baking notes, and kitchen
  appliance manuals.
- **Why:** keeps the BakeFix name and baking corpus, and makes the Vellora
  espresso-machine manual a natural demo document.
- **Rejected:** home bakers only (the Vellora demo would not fit); a generic
  "ask any document" assistant (BakeFix branding would no longer match).

### Navigation
- **Decision:** Ask is the only main view. Words analytics and the evaluation
  runner move to a secondary "Behind the answers" area in the header, one
  click away, each with "Back to asking".
- **Why:** they are required (V2) but are developer tools a home cook does not
  need. **Rejected:** keeping them as equal tabs; hiding them in the footer.

### Kestrel
- **Decision:** Kestrel stays selectable as "Sample: Kestrel Analytics (demo
  company)" with a one-line explanation; "My documents" is the default.
- **Why:** the Concept Map and graph retrieval only work on Kestrel.
- **Rejected:** moving Kestrel to the developer area only.

### Technical controls and details
- **Decision:** document scope, retrieval methods, and chunk settings sit under
  a collapsed "Search options" panel below the ask button ("Most people never
  need these"). Retrieval ranks and scores are collapsed under "technical
  details" in each answer.
- **Why:** a first-time user should see a question box, not RAG parameters.

### States, errors, and destructive actions
- **Decision:** loading, empty library, failed load, "not in your documents",
  and errors each say what to do next. Backend error codes are mapped to plain
  messages (e.g. a missing API key explains how to set it up); "Try again"
  appears only when retrying can help. Removing a document asks for an inline
  confirmation.
- **Why:** raw backend messages ("Gemini cited chunk …") meant nothing to a
  user; deletion is irreversible.

### Answers and sources
- **Decision:** answers are rendered as Markdown (steps keep their numbering);
  sources are numbered `[1]`, `[2]` under "Where this comes from" with a clean
  quote; example questions match the selected knowledge base.

## New feature: answer style controls (Part B, integration)

- **Decision:** a folded "Answer style" control next to the question shows the
  current style as a sentence ("for a beginner · friendly · medium"). Inside:
  "Explain it like I'm 12", reading level, length, tone, and a reset. The
  choice is remembered in the browser only.
- **ELI12 and level:** "Explain it like I'm 12" disables the level choice and
  sends beginner, so the model never receives "expert" and "12-year-old"
  together.
- **Each answer states the style it was written in**, captured when the
  question was sent.
- **Glossary:** "Words to know" under the sources; each definition shows the
  number of the source it was defined from. Malformed entries are skipped in
  the UI rather than hiding the answer.
- **Rejected:** putting style inside "Search options" (it is a reader choice,
  not a search setting); always-visible controls (too much on the page).

## Responsible AI: quarantine review (Part C, integration)

- **API:** `GET /api/quarantine` lists held documents with their findings
  (rule, line, short masked excerpt) but never the document text.
  `POST /api/quarantine/{id}/release` requires `{"approved": true}` in the
  body; `POST /api/quarantine/{id}/reject` discards the text. Release and
  reject each create an indexing trace, like uploads.
- **Errors:** an unknown item is 404; a second release or a release after
  rejection is 409; a release whose file name now exists in the library is
  409 with "Remove it first, then add this one", and the item stays held.
- **Review screen:** a "Held for review" box in the library, shown only when
  something is held. Each finding shows a plain-language reason ("Tries to
  override the assistant's instructions") instead of the rule ID, a risk
  level, the line, and the excerpt.
- **Explicit approval:** "Add anyway" stays disabled until the user ticks
  "I've read these passages and trust this document". Discarding asks for an
  inline confirmation because the held text is deleted.
- **Why the user decides:** the scanner is rule-based and can be wrong in both
  directions (Person A measured false positives), so it holds rather than
  blocks, and the person who knows the document makes the call.
- **Rejected:** a separate review page (the user would have to find it);
  releasing with a single click (no real review); showing the full document
  text (it could contain the very instructions we are holding back, and the
  backend deliberately never returns it).

## Open points to resolve with the team

- Person B: record the answer style in the `llm_generation` span; consider
  dropping an invalid glossary entry instead of rejecting the whole answer
  (a robustness case I reproduced with a fake model, not observed with
  Gemini); finish the before/after redaction evaluation.
- Person A: a delete trace's outcome reads `indexed`; `deleted` would be
  clearer.
