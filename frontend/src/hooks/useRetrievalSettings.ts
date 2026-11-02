import { useReducer } from "react";

type SettingsValues = {
  chunk_size: string;
  overlap: string;
  top_k: string;
};

type RetrievalSettings = {
  chunk_size: number;
  overlap: number;
  top_k: number;
};

type SettingsResponse = RetrievalSettings & {
  index: {
    chunks: number;
  };
};

type SettingsState = {
  values: SettingsValues;
  activeTopK: number;
  phase: "idle" | "saving" | "success" | "error";
  message: string;
};

type SettingsAction =
  | { type: "setting/changed"; field: keyof SettingsValues; value: string }
  | { type: "save/started" }
  | { type: "save/succeeded"; response: SettingsResponse }
  | { type: "save/failed"; message: string };

const INITIAL_STATE: SettingsState = {
  values: {
    chunk_size: "800",
    overlap: "80",
    top_k: "3",
  },
  activeTopK: 3,
  phase: "idle",
  message: "",
};

function settingsReducer(
  state: SettingsState,
  action: SettingsAction,
): SettingsState {
  switch (action.type) {
    case "setting/changed":
      return {
        ...state,
        values: {
          ...state.values,
          [action.field]: action.value,
        },
        phase: "idle",
        message: "",
      };

    case "save/started":
      return {
        ...state,
        phase: "saving",
        message: "Saving settings and rebuilding the index...",
      };

    case "save/succeeded":
      return {
        values: {
          chunk_size: String(action.response.chunk_size),
          overlap: String(action.response.overlap),
          top_k: String(action.response.top_k),
        },
        activeTopK: action.response.top_k,
        phase: "success",
        message: `Settings saved. The index now has ${action.response.index.chunks} chunks.`,
      };

    case "save/failed":
      return {
        ...state,
        phase: "error",
        message: action.message,
      };

    default: {
      const exhaustiveCheck: never = action;
      throw new Error(`Unknown settings action: ${exhaustiveCheck}`);
    }
  }
}

function getValidationError(settings: SettingsValues): string | null {
  const chunkSize = Number(settings.chunk_size);
  const overlap = Number(settings.overlap);
  const topK = Number(settings.top_k);

  if (!Number.isInteger(chunkSize) || chunkSize < 100 || chunkSize > 2000) {
    return "Chunk size must be a whole number from 100 to 2000.";
  }

  if (
    !Number.isInteger(overlap) ||
    overlap < 0 ||
    overlap > 1000 ||
    overlap >= chunkSize
  ) {
    return "Overlap must be from 0 to 1000 and smaller than chunk size.";
  }

  if (!Number.isInteger(topK) || topK < 1 || topK > 20) {
    return "Top-k must be a whole number from 1 to 20.";
  }

  return null;
}

function getApiErrorMessage(value: unknown, fallback: string): string {
  if (typeof value !== "object" || value === null) {
    return fallback;
  }

  const error = (value as Record<string, unknown>).error;
  if (typeof error !== "object" || error === null) {
    return fallback;
  }

  const message = (error as Record<string, unknown>).message;
  return typeof message === "string" ? message : fallback;
}

function isSettingsResponse(value: unknown): value is SettingsResponse {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const response = value as Record<string, unknown>;
  const index = response.index;

  return (
    typeof response.chunk_size === "number" &&
    typeof response.overlap === "number" &&
    typeof response.top_k === "number" &&
    typeof index === "object" &&
    index !== null &&
    typeof (index as Record<string, unknown>).chunks === "number"
  );
}

export function useRetrievalSettings() {
  const [state, dispatch] = useReducer(settingsReducer, INITIAL_STATE);

  async function saveSettings() {
    const validationError = getValidationError(state.values);
    if (validationError) {
      dispatch({ type: "save/failed", message: validationError });
      return;
    }

    dispatch({ type: "save/started" });

    try {
      const response = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chunk_size: Number(state.values.chunk_size),
          overlap: Number(state.values.overlap),
          top_k: Number(state.values.top_k),
        }),
      });

      const data: unknown = await response.json();

      if (!response.ok) {
        throw new Error(
          getApiErrorMessage(data, "Settings could not be saved."),
        );
      }

      if (!isSettingsResponse(data)) {
        throw new Error("The server returned an invalid settings response.");
      }

      dispatch({ type: "save/succeeded", response: data });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Settings could not be saved.";

      dispatch({ type: "save/failed", message });
    }
  }

  function updateSetting(field: keyof SettingsValues, value: string) {
    dispatch({ type: "setting/changed", field, value });
  }

  return {
    settings: state.values,
    activeTopK: state.activeTopK,
    isSaving: state.phase === "saving",
    message: state.message,
    hasError: state.phase === "error",
    updateSetting,
    saveSettings,
  };
}
