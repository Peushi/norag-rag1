import { useState, type FormEvent, type ChangeEvent } from "react";
import {
  getApiErrorMessage,
  getTraceId,
  readJson,
  type DocumentSummary,
  type IndexingActivity,
} from "../types/api";
import { TraceDetails } from "./TraceDetails";

type DocumentLibraryProps = {
  documents: DocumentSummary[];
  isLoading: boolean;
  loadError: string;
  onRetryLoad: () => void;
  onDelete: (document: DocumentSummary) => Promise<IndexingActivity>;
  onUploaded: () => Promise<void>;
};

export function DocumentLibrary({
  documents,
  isLoading,
  loadError,
  onRetryLoad,
  onDelete,
  onUploaded,
}: DocumentLibraryProps) {
  const [activity, setActivity] = useState<IndexingActivity | null>(null);
  const [busyDocumentId, setBusyDocumentId] = useState<string | null>(null);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);

  async function handleDelete(document: DocumentSummary) {
    setConfirmingId(null);
    setBusyDocumentId(document.id);
    setActivity({
      message: `Removing “${document.name}” and updating search…`,
      tone: "success",
      traceId: null,
    });
    try {
      setActivity(await onDelete(document));
    } finally {
      setBusyDocumentId(null);
    }
  }

  return (
    <aside className="card library-card" aria-labelledby="library-title">
      <div className="section-heading">
        <span className="section-icon" aria-hidden="true">
          +
        </span>
        <div>
          <h2 id="library-title">Your documents</h2>
          <p>Recipes, baking notes and appliance manuals that BakeFix searches.</p>
        </div>
      </div>

      <DocumentUpload onUploaded={onUploaded} onActivity={setActivity} />

      {activity && <IndexingActivityNote activity={activity} />}

      <div className="library-documents">
        <div className="library-label">
          <span>Available documents</span>
          <span className="document-count">{documents.length}</span>
        </div>

        <div className="document-list">
          {isLoading && documents.length === 0 ? (
            <div className="empty-library" role="status">
              Loading your documents…
            </div>
          ) : loadError ? (
            <div className="empty-library library-error" role="alert">
              <p>Your documents couldn’t be loaded: {loadError}</p>
              <button type="button" className="button secondary" onClick={onRetryLoad}>
                Try again
              </button>
            </div>
          ) : documents.length === 0 ? (
            <div className="empty-library">
              No documents yet. Add a recipe, note or appliance manual as a
              <strong> .md</strong> or <strong>.txt</strong> file, then ask your
              first question.
            </div>
          ) : (
            <ul>
              {documents.map((document) => (
                <li key={document.id}>
                  <span className="document-name" title={document.name}>
                    {document.name}
                  </span>
                  {confirmingId === document.id ? (
                    <span className="delete-confirm">
                      <span>Remove from BakeFix?</span>
                      <button
                        type="button"
                        className="delete-doc danger"
                        onClick={() => void handleDelete(document)}
                      >
                        Remove
                      </button>
                      <button
                        type="button"
                        className="delete-doc"
                        onClick={() => setConfirmingId(null)}
                      >
                        Cancel
                      </button>
                    </span>
                  ) : (
                    <button
                      type="button"
                      className="delete-doc"
                      aria-label={`Remove ${document.name}`}
                      disabled={busyDocumentId !== null}
                      onClick={() => setConfirmingId(document.id)}
                    >
                      {busyDocumentId === document.id ? "Removing…" : "Remove"}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </aside>
  );
}

/** The outcome of the last upload or removal, with a link to its indexing trace. */
function IndexingActivityNote({ activity }: { activity: IndexingActivity }) {
  return (
    <div
      className={`indexing-activity ${activity.tone}`}
      role={activity.tone === "error" ? "alert" : "status"}
    >
      <p>{activity.message}</p>
      <TraceDetails key={activity.traceId ?? "none"} traceId={activity.traceId} />
    </div>
  );
}

type UploadResponse = {
  status: "indexed" | "quarantined";
  findings?: unknown[];
};

function isUploadResponse(value: unknown): value is UploadResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    "status" in value &&
    (value.status === "indexed" || value.status === "quarantined")
  );
}

type DocumentUploadProps = {
  onUploaded: () => Promise<void>;
  onActivity: (activity: IndexingActivity | null) => void;
};

function DocumentUpload({ onUploaded, onActivity }: DocumentUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!file) {
      onActivity({
        message: "Choose a document to add.",
        tone: "error",
        traceId: null,
      });
      return;
    }

    const fileName = file.name;
    setIsUploading(true);
    onActivity({
      message: `Checking and indexing “${fileName}”…`,
      tone: "success",
      traceId: null,
    });

    let traceId: string | null = null;
    try {
      const body = new FormData();
      body.append("file", file);
      const response = await fetch("/api/documents", {
        method: "POST",
        body,
      });
      const data = await readJson(response);
      traceId = getTraceId(response, data);

      if (!response.ok) {
        throw new Error(
          getApiErrorMessage(data, `“${fileName}” could not be added.`),
        );
      }
      if (!isUploadResponse(data)) {
        throw new Error("The server returned an unexpected upload response.");
      }

      setFile(null);
      form.reset();

      if (data.status === "quarantined") {
        const count = data.findings?.length ?? 0;
        onActivity({
          message:
            `“${fileName}” was held for review and is not searchable yet. ` +
            `It contains ${count === 1 ? "a passage" : `${count} passages`} ` +
            "that look like instructions aimed at the assistant.",
          tone: "warning",
          traceId,
        });
        return;
      }

      await onUploaded().catch(() => undefined);
      onActivity({
        message: `“${fileName}” is ready to search.`,
        tone: "success",
        traceId,
      });
    } catch (error) {
      onActivity({
        message:
          error instanceof Error
            ? error.message
            : `“${fileName}” could not be added.`,
        tone: "error",
        traceId,
      });
    } finally {
      setIsUploading(false);
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null);
    onActivity(null);
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
    </form>
  );
}
