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

The team agreed that BakeFix is for home bakers and will use baking recipes as
its corpus. The current files in `docs/` do not yet match that decision: they
include literary text and an espresso-machine manual. Replace or move those
sample documents out of the indexed corpus when the agreed baking recipes are
available; do not silently index them as BakeFix baking content.

## Audience-focused design recommendations

- Keep the warm visual identity, but bring the question field higher on the
  page so users can get help quickly.
- Use practical, reassuring copy. Make clear that answers come from the user's
  notes and may not cover every baking situation.
- Provide baking-specific example questions, such as "Why didn't my dough
  rise?", and tell users that `.txt` and `.md` notes can be added.
- If supported by the corpus, offer optional starting topics such as dough,
  ovens, ingredients, and storage.
- Make cited source documents and supporting passages easy to inspect.
- Keep examples and UI labels tied to common recipe questions and recipe
  terminology.
