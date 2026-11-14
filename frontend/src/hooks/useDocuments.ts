import { useState } from "react";
import {
  getApiErrorMessage,
  isDocumentSummary,
  type DocumentSummary,
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

  async function deleteDocument(document: DocumentSummary): Promise<void> {
    setStatus(`Removing ${document.name}...`);
    try {
      const response = await fetch(
        `/api/documents/${encodeURIComponent(document.id)}`,
        { method: "DELETE" },
      );
      const data: unknown = await response.json();

      if (!response.ok) {
        throw new Error(
          getApiErrorMessage(data, "That note could not be removed."),
        );
      }

      await loadDocuments();
      setStatus("The note has been removed.");
    } catch (error) {
      setStatus(
        error instanceof Error
          ? error.message
          : "That note could not be removed.",
      );
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
