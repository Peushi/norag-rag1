import { useEffect, useState } from "react";
import { AnswerPanel } from "./components/AnswerPanel";
import { DocumentLibrary } from "./components/DocumentLibrary";
import { DocumentSelector } from "./components/DocumentSelector";
import { EvaluationRunner } from "./components/EvaluationRunner";
import { RetrievalSettings } from "./components/RetrievalSettings";
import { RetrievalComparison } from "./components/RetrievalComparison";
import { WordsExperience } from "./components/WordsExperience";
import { useAskQuestion } from "./hooks/useAskQuestion";
import { useDocumentSelection } from "./hooks/useDocumentSelection";
import { useDocuments } from "./hooks/useDocuments";
import { useRetrievalSettings } from "./hooks/useRetrievalSettings";
import type { EvaluationDataset } from "./types/evaluations";
import "../styles/option-1.css";
import "../styles/option-2.css";
import "../styles/option-3.css";
import "../styles/preview.css";

const DESIGN_OPTIONS = ["1", "2", "3"] as const;
type DesignOption = (typeof DESIGN_OPTIONS)[number];
type AppTab = "ask" | "words" | "evaluation";

function getInitialDesignOption(): DesignOption {
  const saved = window.localStorage.getItem("bakefix-design-option");
  return DESIGN_OPTIONS.find((option) => option === saved) ?? "1";
}

export default function App() {
  const [designOption, setDesignOption] = useState<DesignOption>(
    getInitialDesignOption,
  );
  const [activeTab, setActiveTab] = useState<AppTab>("ask");
  const [selectedCorpus, setSelectedCorpus] =
    useState<EvaluationDataset>("baking");
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
  } = useRetrievalSettings();
  const {
    question,
    setQuestion,
    answer,
    status: questionStatus,
    askQuestion,
    handleQuestionKeyDown,
  } = useAskQuestion({
    documentCount: documents.length,
    selectedDocumentIds,
    topK: activeTopK,
  });

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

  useEffect(() => {
    document.documentElement.dataset.design = designOption;
    window.localStorage.setItem("bakefix-design-option", designOption);
  }, [designOption]);

  const status = questionStatus || documentStatus;

  return (
    <div className="page-shell">
      <header className="masthead">
        <a className="brand" href="/" aria-label="BakeFix home">
          <span className="brand-mark" aria-hidden="true">
            B
          </span>
          <span className="brand-name">BakeFix</span>
        </a>
        <span className="header-note">A calm corner for baking questions</span>
        <div
          className="design-switcher"
          role="group"
          aria-label="Preview design options"
        >
          {DESIGN_OPTIONS.map((option) => (
            <button
              key={option}
              type="button"
              className={`design-option${designOption === option ? " active" : ""}`}
              aria-pressed={designOption === option}
              onClick={() => setDesignOption(option)}
            >
              Option {option}
            </button>
          ))}
        </div>
      </header>

      <section className="intro" aria-labelledby="page-title">
        <p className="eyebrow">
          {activeTab === "ask"
            ? "Good baking starts with a little know-how"
            : activeTab === "words"
              ? "Explore the words behind your answers"
              : "Measure retrieval against labeled evidence"}
        </p>
        <h1 id="page-title">
          {activeTab === "ask" ? (
            <>
              Let&apos;s make your next bake
              <br />
              <em>a little easier.</em>
            </>
          ) : activeTab === "words" ? (
            <>
              Get to know your
              <br />
              <em>knowledge base.</em>
            </>
          ) : (
            <>
              See how well
              <br />
              <em>retrieval performs.</em>
            </>
          )}
        </h1>
        <p className="intro-copy">
          {activeTab === "ask"
            ? "Ask what's on your mind. BakeFix will look through your kitchen notes and bring back the helpful bits, with sources you can check."
            : activeTab === "words"
              ? "See which words appear in the corpus, how often they occur, and which chunks contain them."
              : "Compare the measured baseline and smaller chunks using hit rate, evidence recall, and per-question results."}
        </p>
      </section>

      <nav className="app-tabs" role="tablist" aria-label="Main views">
        <button
          id="ask-tab"
          className={activeTab === "ask" ? "active" : ""}
          type="button"
          role="tab"
          aria-selected={activeTab === "ask"}
          aria-controls="ask-panel"
          onClick={() => setActiveTab("ask")}
        >
          Ask
        </button>
        <button
          id="words-tab"
          className={activeTab === "words" ? "active" : ""}
          type="button"
          role="tab"
          aria-selected={activeTab === "words"}
          aria-controls="words-panel"
          onClick={() => setActiveTab("words")}
        >
          Words
        </button>
        <button
          id="evaluation-tab"
          className={activeTab === "evaluation" ? "active" : ""}
          type="button"
          role="tab"
          aria-selected={activeTab === "evaluation"}
          aria-controls="evaluation-panel"
          onClick={() => setActiveTab("evaluation")}
        >
          Evaluation
        </button>
      </nav>

      <div
        id="ask-panel"
        className="workspace"
        role="tabpanel"
        aria-labelledby="ask-tab"
        hidden={activeTab !== "ask"}
      >
        <DocumentLibrary
          documents={documents}
          onDelete={(item) => void deleteDocument(item)}
          onUploaded={loadDocuments}
        />

        <main className="card question-card">
          <div className="section-heading">
            <span className="section-icon" aria-hidden="true">
              ?
            </span>
            <div>
              <h2>What&apos;s happening in your kitchen?</h2>
              <p>No question is too small. Start wherever you are.</p>
            </div>
          </div>

          <label className="question-label" htmlFor="question">
            Tell us what you&apos;d like to know
          </label>
          <textarea
            id="question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={handleQuestionKeyDown}
            placeholder="For example: Why is my dough not rising?"
          />

          <DocumentSelector
            documents={documents}
            isLoading={isLoadingDocuments}
            selectedDocumentIds={selectedDocumentIds}
            dispatch={selectionDispatch}
          />

          <RetrievalSettings
            settings={settings}
            updateSetting={updateSetting}
            saveSettings={saveSettings}
            isSaving={isSaving}
            message={settingsMessage}
            hasError={settingsHasError}
          />

          <div className="question-actions">
            <span className="helper-copy">
              Answers are based on the documents on your shelf.
            </span>
            <button
              className="button"
              type="button"
              onClick={() => void askQuestion()}
              disabled={answer.kind === "loading"}
            >
              Find an answer <span aria-hidden="true">→</span>
            </button>
          </div>
          <div id="status" role="status" aria-live="polite">
            {status}
            {isLoadingDocuments && !status ? "Loading your notes..." : ""}
          </div>

          <section
            className="answer-box"
            aria-live="polite"
            aria-busy={answer.kind === "loading"}
          >
            <AnswerPanel answer={answer} />
          </section>
        </main>
      </div>
      <div
        id="words-panel"
        role="tabpanel"
        aria-labelledby="words-tab"
        hidden={activeTab !== "words"}
      >
        <WordsExperience
          corpus={selectedCorpus}
          onCorpusChange={setSelectedCorpus}
        />
      </div>
      <div
        id="evaluation-panel"
        className="evaluation-panel"
        role="tabpanel"
        aria-labelledby="evaluation-tab"
        hidden={activeTab !== "evaluation"}
      >
        <EvaluationRunner
          key={selectedCorpus}
          dataset={selectedCorpus}
          onDatasetChange={setSelectedCorpus}
        />
        <RetrievalComparison dataset={selectedCorpus} />
      </div>

      <p className="footer-note">
        Made for curious bakers, one question at a time.
      </p>
    </div>
  );
}
