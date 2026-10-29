import { useEffect, useState } from "react";

const EMPTY_ANSWER = {
  kind: "empty",
  text: "Your answer will feel right at home here.",
};

function getErrorMessage(data, fallback) {
  return data?.error?.message || fallback;
}

function DocumentLibrary({ documents, onDelete, onUploaded }) {
  return (
    <aside className="card library-card" aria-labelledby="library-title">
      <div className="section-heading">
        <span className="section-icon" aria-hidden="true">
          +
        </span>
        <div>
          <h2 id="library-title">Your recipe shelf</h2>
          <p>Keep your baking notes close.</p>
        </div>
      </div>

      <DocumentUpload onUploaded={onUploaded} />

      <div className="library-label">
        <span>Available notes</span>
        <span className="document-count">{documents.length}</span>
      </div>

      <div className="document-list">
        {documents.length === 0 ? (
          <div className="empty-library">
            Your shelf is ready when you are. Add a note to get started.
          </div>
        ) : (
          <ul>
            {documents.map((document) => (
              <li key={document.id}>
                <span className="document-name" title={document.name}>
                  {document.name}
                </span>
                <button
                  type="button"
                  className="delete-doc"
                  aria-label={`Remove ${document.name}`}
                  onClick={() => onDelete(document)}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}

function DocumentUpload({ onUploaded }) {
  const [file, setFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState("");
  const [uploadError, setUploadError] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!file) {
      setUploadError(true);
      setUploadMessage("Choose a note to add to your shelf.");
      return;
    }

    setIsUploading(true);
    setUploadError(false);
    setUploadMessage("Adding your note...");

    try {
      const body = new FormData();
      body.append("file", file);
      const response = await fetch("/api/documents", {
        method: "POST",
        body,
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(getErrorMessage(data, "That note could not be added."));
      }

      setFile(null);
      form.reset();
      await onUploaded();
      setUploadMessage("Your note is on the shelf.");
    } catch (error) {
      setUploadError(true);
      setUploadMessage(error.message || "That note could not be added.");
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <form className="upload-box" onSubmit={handleSubmit}>
      <label htmlFor="file-input">Add a document</label>
      <input
        type="file"
        id="file-input"
        name="file"
        accept=".txt,.md,text/plain,text/markdown"
        onChange={(event) => {
          setFile(event.target.files?.[0] ?? null);
          setUploadMessage("");
        }}
      />
      <button className="button upload-button" type="submit" disabled={isUploading}>
        {isUploading ? "Adding note..." : "Add to my shelf"}
      </button>
      {uploadMessage && (
        <p className={`upload-message${uploadError ? " error" : ""}`} role="status">
          {uploadMessage}
        </p>
      )}
    </form>
  );
}

function AnswerPanel({ answer }) {
  if (answer.kind === "loading") {
    return (
      <div className="answer-placeholder">
        <span className="placeholder-mark" aria-hidden="true">
          ~
        </span>
        <p>Gathering the helpful bits...</p>
      </div>
    );
  }

  if (answer.kind === "error") {
    return (
      <div className="error">
        <p>{answer.text}</p>
      </div>
    );
  }

  if (answer.kind === "empty") {
    return (
      <div className="answer-placeholder">
        <span className="placeholder-mark" aria-hidden="true">
          ~
        </span>
        <p>{answer.text}</p>
      </div>
    );
  }

  if (answer.kind === "not_found") {
    return (
      <>
        <div className="answer-title">Not in your notes yet</div>
        <p className="answer-copy not-found">{answer.text}</p>
      </>
    );
  }

  return (
    <>
      <div className="answer-title">A little guidance</div>
      <p className="answer-copy">{answer.text}</p>
      {answer.references.length > 0 && (
        <div className="references">
          <h3>From your notes</h3>
          <ul>
            {answer.references.map((reference) => (
              <li key={`${reference.chunk_id}-${reference.position}`}>
                <span className="reference-meta">
                  {reference.source} · note {reference.position + 1}
                </span>
                <span className="reference-quote">“{reference.quote}”</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}

export default function App() {
  const [documents, setDocuments] = useState([]);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(EMPTY_ANSWER);
  const [status, setStatus] = useState("");
  const [isLoadingDocuments, setIsLoadingDocuments] = useState(true);

  async function loadDocuments() {
    try {
      const response = await fetch("/api/documents");
      const data = await response.json();
      if (!response.ok) {
        throw new Error(getErrorMessage(data, "Could not load your notes."));
      }
      setDocuments(data.documents ?? []);
    } catch (error) {
      setStatus(error.message || "Could not load your notes.");
    } finally {
      setIsLoadingDocuments(false);
    }
  }

  useEffect(() => {
    loadDocuments();
  }, []);

  async function deleteDocument(document) {
    setStatus(`Removing ${document.name}...`);
    try {
      const response = await fetch(
        `/api/documents/${encodeURIComponent(document.id)}`,
        { method: "DELETE" },
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(getErrorMessage(data, "That note could not be removed."));
      }
      await loadDocuments();
      setStatus("The note has been removed.");
    } catch (error) {
      setStatus(error.message || "That note could not be removed.");
    }
  }

  async function askQuestion() {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) {
      setStatus("Write a question first, and we’ll take it from there.");
      return;
    }

    setStatus("Looking through your notes...");
    setAnswer({ kind: "loading" });

    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: trimmedQuestion, top_k: 4 }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(getErrorMessage(data, "Something went wrong. Please try again."));
      }

      if (data.status === "not_found") {
        setAnswer({ kind: "not_found", text: data.answer });
        setStatus("No matching note found.");
      } else {
        setAnswer({
          kind: "answered",
          text: data.answer,
          references: data.references ?? [],
        });
        setStatus("Here’s what I found.");
      }
    } catch (error) {
      setAnswer({
        kind: "error",
        text: error.message || "Something went wrong. Please try again.",
      });
      setStatus("We couldn’t find an answer just now.");
    }
  }

  function handleQuestionKeyDown(event) {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      askQuestion();
    }
  }

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
          onDelete={deleteDocument}
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
          <div className="question-actions">
            <span className="helper-copy">
              Answers are based on the documents on your shelf.
            </span>
            <button
              className="button"
              type="button"
              onClick={askQuestion}
              disabled={answer.kind === "loading"}
            >
              Find an answer <span aria-hidden="true">→</span>
            </button>
          </div>
          <div id="status" role="status" aria-live="polite">
            {status}
            {isLoadingDocuments && !status ? "Loading your notes..." : ""}
          </div>

          <section className="answer-box" aria-live="polite" aria-busy={answer.kind === "loading"}>
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
