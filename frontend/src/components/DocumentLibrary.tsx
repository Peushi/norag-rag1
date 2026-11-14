import { useState, type FormEvent, type ChangeEvent } from "react";
import { getApiErrorMessage, type DocumentSummary } from "../types/api";

type DocumentLibraryProps = {
  documents: DocumentSummary[];
  onDelete: (document: DocumentSummary) => void;
  onUploaded: () => Promise<void>;
};

export function DocumentLibrary({
  documents,
  onDelete,
  onUploaded,
}: DocumentLibraryProps) {
  return (
    <aside className="card library-card" aria-labelledby="library-title">
      <div className="section-heading">
        <span className="section-icon" aria-hidden="true">
          +
        </span>
        <div>
          <h2 id="library-title">Your documents</h2>
          <p>Add manuals and notes for BakeFix to search.</p>
        </div>
      </div>

      <DocumentUpload onUploaded={onUploaded} />

      <div className="library-documents">
        <div className="library-label">
          <span>Available documents</span>
          <span className="document-count">{documents.length}</span>
        </div>

        <div className="document-list">
          {documents.length === 0 ? (
            <div className="empty-library">
              No documents yet. Add a Markdown or text file to get started.
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
      </div>
    </aside>
  );
}

type DocumentUploadProps = {
  onUploaded: () => Promise<void>;
};

function DocumentUpload({ onUploaded }: DocumentUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState("");
  const [uploadError, setUploadError] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!file) {
      setUploadError(true);
      setUploadMessage("Choose a document to add.");
      return;
    }

    setIsUploading(true);
    setUploadError(false);
    setUploadMessage("Adding and indexing your document...");

    try {
      const body = new FormData();
      body.append("file", file);
      const response = await fetch("/api/documents", {
        method: "POST",
        body,
      });
      const data: unknown = await response.json();

      if (!response.ok) {
        throw new Error(
          getApiErrorMessage(data, "That document could not be added."),
        );
      }

      setFile(null);
      form.reset();
      await onUploaded();
      setUploadMessage("Your document is ready to search.");
    } catch (error) {
      setUploadError(true);
      setUploadMessage(
        error instanceof Error
          ? error.message
          : "That document could not be added.",
      );
    } finally {
      setIsUploading(false);
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null);
    setUploadMessage("");
  }

  return (
    <form className="upload-box" onSubmit={(event) => void handleSubmit(event)}>
      <label htmlFor="file-input">Choose a document (.md or .txt)</label>
      <input
        type="file"
        id="file-input"
        name="file"
        accept=".txt,.md,text/plain,text/markdown"
        onChange={handleFileChange}
      />
      <button
        className="button upload-button"
        type="submit"
        disabled={isUploading}
      >
        {isUploading ? "Adding document..." : "Add document"}
      </button>
      {uploadMessage && (
        <p
          className={`upload-message${uploadError ? " error" : ""}`}
          role="status"
        >
          {uploadMessage}
        </p>
      )}
    </form>
  );
}
