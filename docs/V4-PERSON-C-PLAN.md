# V4 Implementation Plan — Person C (Aleksandra)

## Completed

1. **Ask trace storage and API integration**
   - Add a local SQLite trace recorder with spans, outcomes, and 30-day expiry.
   - Create a trace for each Ask API request and pass it to
     `ask_question(trace=trace)`.
   - Return the trace ID on successful answers and expose it in the
     `X-Trace-ID` header on API errors.
   - Provide `GET /api/traces/{trace_id}`.
2. **Generation trace Details UI**
   - Add a Details panel to answers and abstentions, showing safe span metadata,
     outcome, statuses, and durations.
   - Integrate Person B's generation spans for redaction, Gemini generation,
     response validation, and citation verification.
3. **Validation**
   - At the time this plan was saved, all 112 backend tests passed and the
     frontend typecheck and production build passed.

## Remaining work, in order

1. **Improve the core user journey**
   - Make it clear what users can ask, which knowledge base is selected, and
     where an answer and its source evidence will appear.
   - Reduce technical controls in the default view; keep advanced retrieval
     choices available without making them the first step.
   - Make loading, empty-library, upload, no-evidence, and error states
     understandable and actionable.
   - Exercise the journey using a realistic document, such as the supplied
     Vellora Duo espresso-machine manual.
2. **Add indexing-run traces**
   - Trace document loading, chunking, embedding/indexing, and failure outcomes
     for index builds caused by upload, deletion, settings changes, or stale
     index refreshes.
   - Coordinate graph-extraction spans and token metadata with Person A.
3. **Integrate Person A's Concept Map and injection scanner**
   - Add the Kestrel-only explorer, relationship evidence, and source navigation
     using Person A's agreed API.
   - Connect upload scanning, quarantine, review, and explicit release; verify
     quarantined documents cannot be indexed before release.
4. **Integrate Person B's answer-style feature**
   - Add beginner/expert, tone, length, and “explain as if I were 12” controls
     using Person B's request contract.
   - Present the grounded glossary while preserving citations, redaction, and
     tracing.
5. **End-to-end V4 verification and release readiness**
   - Test successful answers, abstentions, failures, indexing traces, answer
     styles, concept-to-source navigation, and quarantine/release.
   - Verify traces never contain API keys, complete documents/chunks, or
     unredacted personal data.
   - Update README and report, confirm first-time installation/run instructions,
     and prepare the presentation flow.
   - Keep the optional metrics dashboard out of scope until required work is
     complete.

## Integration boundaries

- Person A owns Concept Map data and injection-scanner logic.
- Person B owns answer-style generation and PII-redaction logic.
- Person C owns shared trace storage/API, frontend experience, feature wiring,
  and end-to-end integration.
- Use one shared API/trace contract; feature owners add spans to the injected
  trace context rather than creating separate trace storage.
- The existing concept graph is Kestrel-only unless graph support is added for
  another corpus.

## Waiting on

- Person A's response and API/behavior contract for Concept Map and injection
  scanning.
- Person B's final answer-style request/response contract and confirmation that
  redaction covers every Gemini call and trace write.
