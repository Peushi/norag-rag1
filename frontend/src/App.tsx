import { useEffect, useState } from "react";
import { AnswerPanel } from "./components/AnswerPanel";
import { DocumentLibrary } from "./components/DocumentLibrary";
import { DocumentSelector } from "./components/DocumentSelector";
import { RetrievalSettings } from "./components/RetrievalSettings";
import { useAskQuestion } from "./hooks/useAskQuestion";
import { useDocumentSelection } from "./hooks/useDocumentSelection";
import { useDocuments } from "./hooks/useDocuments";
import { useRetrievalSettings } from "./hooks/useRetrievalSettings";
import "../styles/option-1.css";
import "../styles/option-2.css";
import "../styles/option-3.css";
import "../styles/preview.css";

const DESIGN_OPTIONS = ["1", "2", "3"] as const;
type DesignOption = (typeof DESIGN_OPTIONS)[number];

function getInitialDesignOption(): DesignOption {
  const saved = window.localStorage.getItem("bakefix-design-option");
  return DESIGN_OPTIONS.find((option) => option === saved) ?? "1";
}

export default function App() {
  const [designOption, setDesignOption] = useState<DesignOption>(
    getInitialDesignOption,
  );
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
        <p className="eyebrow">Good baking starts with a little know-how</p>
        <h1 id="page-title">
          Let&apos;s make your next bake
          <br />
          <em>a little easier.</em>
        </h1>
        <p className="intro-copy">
          Ask what&apos;s on your mind. BakeFix will look through your kitchen
          notes and bring back the helpful bits, with sources you can check.
        </p>
      </section>

      <div className="workspace">
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

      <p className="footer-note">
        Made for curious bakers, one question at a time.
      </p>
    </div>
  );
}
