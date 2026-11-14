import { useState } from "react";
import {
  getApiErrorMessage,
  getTraceId,
  isDocumentSummary,
  readJson,
  type DocumentSummary,
  type IndexingActivity,
} from "../types/api";

export function useDocuments() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [status, setStatus] = useState("");

  async function loadDocuments(): Promise<void> {
    setIsLoading(true);
    try {
      const response = await fetch("/api/documents");
      const data: unknown = await response.json();

      if (!response.ok) {
        throw new Error(
          getApiErrorMessage(data, "Could not load your documents."),
        );
      }

      if (
        typeof data !== "object" ||
        data === null ||
        !("documents" in data) ||
        !Array.isArray(data.documents) ||
        !data.documents.every(isDocumentSummary)
      ) {
        throw new Error("The server returned an invalid document list.");
      }

      setDocuments(data.documents);
      setStatus("");
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Could not load your documents.";
      setStatus(message);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }

  /** Remove a document; the library shows the returned outcome and its trace. */
  async function deleteDocument(
    document: DocumentSummary,
  ): Promise<IndexingActivity> {
    let traceId: string | null = null;
    try {
      const response = await fetch(
        `/api/documents/${encodeURIComponent(document.id)}`,
        { method: "DELETE" },
      );
      const data = await readJson(response);
      traceId = getTraceId(response, data);

      if (!response.ok) {
        throw new Error(
          getApiErrorMessage(data, `“${document.name}” could not be removed.`),
        );
      }

      await loadDocuments().catch(() => undefined);
      return {
        message: `“${document.name}” was removed and is no longer searched.`,
        tone: "success",
        traceId,
      };
    } catch (error) {
      return {
        message:
          error instanceof Error
            ? error.message
            : `“${document.name}” could not be removed.`,
        tone: "error",
        traceId,
      };
    }
  }

  return {
    documents,
    isLoading,
    status,
    setStatus,
    loadDocuments,
    deleteDocument,
  };
}
