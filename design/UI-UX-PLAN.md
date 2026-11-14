# BakeFix UI/UX Improvement Plan

## Goal

Improve clarity, user control, and trust while preserving BakeFix's warm visual
identity and keeping the frontend as a React client of the FastAPI API.

## Priorities

1. **Make references verifiable**
   - Let users open or expand each answer reference.
   - Fetch and display the full retrieved passage through
     `/api/chunks/{chunk_id}`.
   - Handle reference-loading and reference-error states accessibly.
2. **Let users choose the search scope**
   - Search all notes by default.
   - Offer an optional selection of documents to include.
   - Send selected IDs in the `/api/ask` request and show the active scope.
3. **Improve task feedback and recovery**
   - Keep upload feedback beside the upload control.
   - Show deletion progress and errors beside the affected document.
   - Keep question errors beside the answer, preserve the question, and prevent
     duplicate submissions while a request is running.
4. **Clarify loading and empty states**
   - Distinguish loading the document list from an empty library and a failed
     load.
   - Explain supported document formats and the next step when the library is
     empty.
5. **Refine task visibility and accessibility**
   - Reduce excessive vertical space so the question appears sooner.
   - Verify keyboard operation, visible focus, contrast, screen-reader status
     announcements, touch targets, responsive layouts, and zoom.

## Suggested sequence

Implement reference previews and document selection first because they improve
trust and user control. Then improve feedback and loading/empty states. Finish
with layout refinements and an accessibility/responsive review.

## Confirmed product audience and corpus

BakeFix is for home cooks: people who bake and want answers from their own
recipes, baking notes, and kitchen appliance manuals. This V4 decision widens
the earlier "home bakers only" scope so that appliance manuals belong in the
library; the Vellora Duo espresso-machine manual in `docs/` is the realistic
document we use to exercise the full journey (upload, ask, open the trace).

The baking guides in `corpus/` are the default "My documents" library. The
Kestrel knowledge base stays available as a clearly labelled sample
("Sample: Kestrel Analytics (demo company)") because the Concept Map explorer
and the graph retriever only work on Kestrel. It is read-only and never mixed
with the user's documents.

## Audience-focused design recommendations

- Keep the warm visual identity, but bring the question field higher on the
  page so users can get help quickly.
- Use practical, reassuring copy. Make clear that answers come only from the
  user's documents and may not cover every kitchen situation.
- Provide example questions that match the selected knowledge base, such as
  "Why didn't my bread dough rise?" for the user's documents, and tell users
  that `.txt` and `.md` recipes, notes, and manuals can be added.
- If supported by the corpus, offer optional starting topics such as dough,
  ovens, ingredients, storage, and appliance care.
- Make cited source documents and supporting passages easy to inspect.
- Keep examples and UI labels in everyday kitchen language; avoid retrieval
  terms (chunks, top-k, RRF) outside "Search options" and technical details.

## V4 navigation and visibility decisions

- **Ask is the only main view.** Words analytics and the evaluation runner are
  developer tools; they moved to a secondary "Behind the answers" area in the
  header, one click away, each with a "Back to asking" link.
- **Technical controls are secondary.** Document scope, retrieval methods, and
  chunk settings live under a collapsed "Search options" panel below the ask
  button. Retrieval ranks and scores sit under a collapsed "technical details"
  section of each answer; the full trace opens from "Details".
- **Every state says what to do next.** Loading, empty library, failed load,
  "not in your documents", and errors each explain the next step; errors only
  offer "Try again" when retrying can help.
- **Destructive actions ask first.** Removing a document needs an inline
  confirmation, and every upload, removal, or settings change shows its
  outcome with a link to its indexing trace.
