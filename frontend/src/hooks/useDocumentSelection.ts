import { useReducer } from "react";

// null means all documents
// an array means only the IDs in that array
// empty array = no documents
type DocumentSelectionState = string[] | null;

type DocumentSelectionAction =
  | { type: "documents/changed"; documentIds: string[] }
  | {
      type: "document/toggled";
      documentId: string;
      checked: boolean;
      documentIds: string[];
    }
  | { type: "selection/cleared" }
  | { type: "selection/all" };

function documentSelectionReducer(
  state: DocumentSelectionState,
  action: DocumentSelectionAction,
): DocumentSelectionState {
  switch (action.type) {
    case "documents/changed": {
      if (state === null) {
        return null;
      }

      const availableIds = new Set(action.documentIds);
      return state.filter((id) => availableIds.has(id));
    }

    case "document/toggled": {
      const currentIds = state ?? action.documentIds;

      const nextIds = action.checked
        ? [...new Set([...currentIds, action.documentId])]
        : currentIds.filter((id) => id !== action.documentId);

      return nextIds.length === action.documentIds.length ? null : nextIds;
    }

    case "selection/cleared":
      return [];

    case "selection/all":
      return null;

    default: {
      // never = there should be no action left unhandled
      const exhaustiveCheck: never = action;
      throw new Error(`Unknown document-selection action: ${exhaustiveCheck}`);
    }
  }
}

export function useDocumentSelection() {
  return useReducer(documentSelectionReducer, null);
}
