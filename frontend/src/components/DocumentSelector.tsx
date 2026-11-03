import type { Dispatch } from "react";
import "../../styles/document-scope.css";
import type { DocumentSummary } from "../types/api";

type SelectionAction =
  | { type: "documents/changed"; documentIds: string[] }
  | {
      type: "document/toggled";
      documentId: string;
      checked: boolean;
      documentIds: string[];
    }
  | { type: "selection/cleared" }
  | { type: "selection/all" };

type DocumentSelectorProps = {
  documents: DocumentSummary[];
  isLoading: boolean;
  selectedDocumentIds: string[] | null;
  dispatch: Dispatch<SelectionAction>;
};

export function DocumentSelector({
  documents,
  isLoading,
  selectedDocumentIds,
  dispatch,
}: DocumentSelectorProps) {
  const documentIds = documents.map((document) => document.id);

  return (
    <fieldset className="document-scope" disabled={isLoading}>
      <legend>Search in</legend>
      {documents.length === 0 ? (
        <p>No documents are available yet. Add one to get started.</p>
      ) : (
        documents.map((document) => (
          <label key={document.id}>
            <input
              type="checkbox"
              checked={
                selectedDocumentIds === null ||
                selectedDocumentIds.includes(document.id)
              }
              onChange={(event) =>
                dispatch({
                  type: "document/toggled",
                  documentId: document.id,
                  checked: event.target.checked,
                  documentIds,
                })
              }
            />
            {document.name}
          </label>
        ))
      )}

      <button
        type="button"
        onClick={() => dispatch({ type: "selection/all" })}
        disabled={isLoading || documents.length === 0}
      >
        Select all
      </button>
      <button
        type="button"
        onClick={() => dispatch({ type: "selection/cleared" })}
        disabled={isLoading || documents.length === 0}
      >
        Clear selection
      </button>
    </fieldset>
  );
}
