import { useEffect, useState } from "react";
import { AnswerPanel } from "./components/AnswerPanel";
import { AnswerStyleControls } from "./components/AnswerStyleControls";
import { DocumentLibrary } from "./components/DocumentLibrary";
import { DocumentSelector } from "./components/DocumentSelector";
import { EvaluationRunner } from "./components/EvaluationRunner";
import { RetrievalSettings } from "./components/RetrievalSettings";
import { RetrievalComparison } from "./components/RetrievalComparison";
import { RetrieverControls } from "./components/RetrieverControls";
import { WordsExperience } from "./components/WordsExperience";
import { useAnswerStyle } from "./hooks/useAnswerStyle";
import { useAskQuestion } from "./hooks/useAskQuestion";
import { useDocumentSelection } from "./hooks/useDocumentSelection";
import { useDocuments } from "./hooks/useDocuments";
import { useRetrievalSettings } from "./hooks/useRetrievalSettings";
import type { EvaluationDataset } from "./types/evaluations";
import type { RetrieverName } from "./types/api";
import "../styles/base.css";
import "../styles/option-1.css";
import "../styles/ask-experience.css";

type AppView = "ask" | "words" | "evaluation";

/** Starter questions shown under the question box, per knowledge base. */
const EXAMPLE_QUESTIONS: Record<EvaluationDataset, string[]> = {
  baking: [
    "Why didn't my bread dough rise?",
    "How do I stop my cookies from spreading?",
    "How do I keep a pie crust from getting soggy?",
  ],
  kestrel: [
    "What does error KST-2044 mean and how do I fix it?",
    "Can I get a refund on my annual plan 45 days after it renewed?",
    "What happens when a customer's card payment fails?",
  ],
};

const INSIGHT_VIEWS: { id: Exclude<AppView, "ask">; label: string }[] = [
  { id: "words", label: "Words in your documents" },
  { id: "evaluation", label: "Answer quality checks" },
];

export default function App() {
  const [activeView, setActiveView] = useState<AppView>("ask");
  const [selectedCorpus, setSelectedCorpus] =
    useState<EvaluationDataset>("baking");
  const [askDataset, setAskDataset] = useState<EvaluationDataset>("baking");
  const [selectedRetrievers, setSelectedRetrievers] =
    useState<RetrieverName[]>(["dense"]);
  const [includePathContext, setIncludePathContext] = useState(false);
  const {
    documents,
    isLoading: isLoadingDocuments,
    status: documentStatus,
    loadDocuments,
    deleteDocument,
  } = useDocuments();
  const [selectedDocumentIds, selectionDispatch] = useDocumentSelection();
  const {
    settings,
    activeTopK,
    updateSetting,
    saveSettings,
    isSaving,
    message: settingsMessage,
    hasError: settingsHasError,
    traceId: settingsTraceId,
  } = useRetrievalSettings();
  const { style: answerStyle, updateStyle, resetStyle } = useAnswerStyle();
  const {
    question,
    setQuestion,
    answer,
    status: questionStatus,
    askQuestion,
    handleQuestionKeyDown,
  } = useAskQuestion({
    documentCount: askDataset === "kestrel" ? 1 : documents.length,
    selectedDocumentIds,
    topK: activeTopK,
    dataset: askDataset,
    retrievers: selectedRetrievers,
    includePathContext,
    style: answerStyle,
  });

  function toggleRetriever(retriever: RetrieverName) {
    if (selectedRetrievers.includes(retriever)) {
      setSelectedRetrievers(
        selectedRetrievers.filter((item) => item !== retriever),
      );
      if (retriever === "graph") {
        setIncludePathContext(false);
      }
      return;
    }
    setSelectedRetrievers([...selectedRetrievers, retriever]);
  }

  function changeAskDataset(dataset: EvaluationDataset) {
    setAskDataset(dataset);
    if (dataset !== "kestrel") {
      // Graph search is Kestrel-only; never leave the user with no method.
      setSelectedRetrievers((current) => {
        const remaining = current.filter((retriever) => retriever !== "graph");
        return remaining.length > 0 ? remaining : ["dense"];
      });
      setIncludePathContext(false);
    }
  }

  useEffect(() => {
    void loadDocuments().catch(() => {
      // The document hook exposes the failure through its status.
    });
  }, []);

  useEffect(() => {
    selectionDispatch({
      type: "documents/changed",
      documentIds: documents.map((document) => document.id),
    });
  }, [documents]);

  const isAskView = activeView === "ask";
  const isKestrel = askDataset === "kestrel";
  const documentLoadError =
    !isLoadingDocuments && documentStatus ? documentStatus : "";
  const isScoped =
    !isKestrel &&
    selectedDocumentIds !== null &&
    selectedDocumentIds.length < documents.length;

  return (
    <div className="page-shell">
      <header className="masthead">
        <button
          type="button"
          className="brand"
          aria-label="BakeFix home"
          onClick={() => setActiveView("ask")}
        >
          <span className="brand-mark" aria-hidden="true">
            B
          </span>
          <span className="brand-name">BakeFix</span>
        </button>
        <nav className="insights-nav" aria-label="Behind the answers">
          <span className="insights-label">Behind the answers:</span>
          {INSIGHT_VIEWS.map((view) => (
            <button
              key={view.id}
              type="button"
              className={activeView === view.id ? "active" : ""}
              aria-current={activeView === view.id ? "page" : undefined}
              onClick={() => setActiveView(view.id)}
            >
              {view.label}
            </button>
          ))}
        </nav>
      </header>

      {isAskView ? (
        <section className="intro intro-compact" aria-labelledby="page-title">
          <h1 id="page-title">
            Kitchen questions, <em>answered from your own documents.</em>
          </h1>
          <p className="intro-copy">
            Add your recipes, baking notes and appliance manuals, then ask.
            Every answer shows the passages it came from.
          </p>
        </section>
      ) : (
        <section className="intro intro-compact" aria-labelledby="page-title">
          <button
            type="button"
            className="back-to-ask"
            onClick={() => setActiveView("ask")}
          >
            <span aria-hidden="true">←</span> Back to asking
          </button>
          <h1 id="page-title">
            {activeView === "words" ? (
              <>
                The words <em>in your documents.</em>
              </>
            ) : (
              <>
                How well <em>BakeFix finds answers.</em>
              </>
            )}
          </h1>
          <p className="intro-copy">
            {activeView === "words"
              ? "See which words appear in your documents, how often, and in which passages. Useful when a question isn't finding what you expect."
              : "Run the fixed test questions and compare search settings using hit rate, evidence recall and per-question results."}
          </p>
        </section>
      )}

      <div className="workspace" hidden={!isAskView}>
        {!isKestrel && (
          <DocumentLibrary
            documents={documents}
            isLoading={isLoadingDocuments}
            loadError={documentLoadError}
            onRetryLoad={() => void loadDocuments().catch(() => undefined)}
            onDelete={deleteDocument}
            onUploaded={loadDocuments}
          />
        )}

        <main className="card question-card">
          <div className="section-heading">
            <span className="section-icon" aria-hidden="true">
              ?
            </span>
            <div>
              <h2>What would you like to know?</h2>
              <p>
                {isKestrel
                  ? "You're asking the Kestrel Analytics sample: a fictional software company's help documents."
                  : "Ask about a recipe, an appliance, or a kitchen problem."}
              </p>
            </div>
          </div>

          <label className="ask-corpus-select" htmlFor="ask-dataset">
            Search in
            <select
              id="ask-dataset"
              value={askDataset}
              onChange={(event) =>
                changeAskDataset(
                  event.target.value === "kestrel" ? "kestrel" : "baking",
                )
              }
            >
              <option value="baking">My documents</option>
              <option value="kestrel">
                Sample: Kestrel Analytics (demo company)
              </option>
            </select>
          </label>
          {isKestrel && (
            <p className="ask-corpus-note">
              This read-only sample shows what BakeFix can do with a larger set
              of help documents. Switch back to “My documents” to ask about
              your own files.
            </p>
          )}

          <label className="question-label" htmlFor="question">
            Your question
          </label>
          <textarea
            id="question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={handleQuestionKeyDown}
            placeholder={
              isKestrel
                ? "For example: what does error KST-4012 mean?"
                : "For example: why are my brownies cakey instead of fudgy?"
            }
          />

          <div className="example-questions" aria-label="Example questions">
            <span>Try:</span>
            {EXAMPLE_QUESTIONS[askDataset].map((example) => (
              <button
                key={example}
                type="button"
                className="example-question"
                onClick={() => setQuestion(example)}
              >
                {example}
              </button>
            ))}
          </div>

          <AnswerStyleControls
            style={answerStyle}
            onChange={updateStyle}
            onReset={resetStyle}
          />

          <div className="question-actions">
            <span className="helper-copy">
              {isKestrel
                ? "Searching the Kestrel sample."
                : isLoadingDocuments && documents.length === 0
                  ? "Loading your documents…"
                  : documents.length === 0
                    ? "Add a document to start asking."
                    : isScoped
                  ? `Searching ${selectedDocumentIds?.length ?? 0} of ${documents.length} documents.`
                  : `Searching all ${documents.length} of your documents.`}
            </span>
            <button
              className="button"
              type="button"
              onClick={() => void askQuestion()}
              disabled={answer.kind === "loading"}
            >
              {answer.kind === "loading" ? "Finding an answer…" : "Find an answer"}{" "}
              <span aria-hidden="true">→</span>
            </button>
          </div>
          <p className="keyboard-hint">Tip: press ⌘/Ctrl + Enter to ask.</p>

          <details className="advanced-search-options">
            <summary>Search options</summary>
            <p className="advanced-search-help">
              Most people never need these. By default BakeFix searches all
              your documents with settings we tested on our question sets.
            </p>
            {!isKestrel && (
              <DocumentSelector
                documents={documents}
                isLoading={isLoadingDocuments}
                selectedDocumentIds={selectedDocumentIds}
                dispatch={selectionDispatch}
              />
            )}

            <RetrieverControls
              dataset={askDataset}
              selectedRetrievers={selectedRetrievers}
              onToggleRetriever={toggleRetriever}
              includePathContext={includePathContext}
              onPathContextChange={setIncludePathContext}
            />

            <RetrievalSettings
              settings={settings}
              updateSetting={updateSetting}
              saveSettings={saveSettings}
              isSaving={isSaving}
              message={settingsMessage}
              hasError={settingsHasError}
              traceId={settingsTraceId}
            />
          </details>

          <div id="status" className="ask-status" role="status" aria-live="polite">
            {questionStatus}
          </div>

          <section
            className="answer-box"
            aria-label="Answer"
            aria-busy={answer.kind === "loading"}
          >
            <AnswerPanel
              answer={answer}
              onRetry={() => void askQuestion()}
            />
          </section>
        </main>
      </div>

      {activeView === "words" && (
        <div id="words-panel">
          <WordsExperience
            corpus={selectedCorpus}
            onCorpusChange={setSelectedCorpus}
          />
        </div>
      )}
      {activeView === "evaluation" && (
        <div id="evaluation-panel" className="evaluation-panel">
          <EvaluationRunner
            key={selectedCorpus}
            dataset={selectedCorpus}
            onDatasetChange={setSelectedCorpus}
          />
          <RetrievalComparison dataset={selectedCorpus} />
        </div>
      )}

      <p className="footer-note">
        BakeFix answers only from the documents you add, so it may not cover
        every kitchen situation. If it can't find an answer, it says so.
      </p>
    </div>
  );
}
