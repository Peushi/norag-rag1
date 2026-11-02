export type DocumentSummary = {
  id: string;
  name: string;
  size_bytes: number;
};

export type AnswerReference = {
  chunk_id: string;
  source: string;
  position: number;
  quote: string;
};

export type AskResponse = {
  status: "answered" | "not_found";
  answer: string;
  references: AnswerReference[];
};

export type Answer =
  | { kind: "empty"; text: string }
  | { kind: "loading" }
  | { kind: "error"; text: string }
  | { kind: "not_found"; text: string }
  | { kind: "answered"; text: string; references: AnswerReference[] };

export function getApiErrorMessage(value: unknown, fallback: string): string {
  if (typeof value !== "object" || value === null || !("error" in value)) {
    return fallback;
  }

  const error = value.error;
  if (typeof error !== "object" || error === null || !("message" in error)) {
    return fallback;
  }

  return typeof error.message === "string" ? error.message : fallback;
}

export function isDocumentSummary(value: unknown): value is DocumentSummary {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  return (
    "id" in value &&
    typeof value.id === "string" &&
    "name" in value &&
    typeof value.name === "string" &&
    "size_bytes" in value &&
    typeof value.size_bytes === "number"
  );
}

export function isAskResponse(value: unknown): value is AskResponse {
  if (
    typeof value !== "object" ||
    value === null ||
    !("status" in value) ||
    (value.status !== "answered" && value.status !== "not_found") ||
    !("answer" in value) ||
    typeof value.answer !== "string" ||
    !("references" in value) ||
    !Array.isArray(value.references)
  ) {
    return false;
  }

  return value.references.every(
    (reference: unknown) =>
      typeof reference === "object" &&
      reference !== null &&
      "chunk_id" in reference &&
      typeof reference.chunk_id === "string" &&
      "source" in reference &&
      typeof reference.source === "string" &&
      "position" in reference &&
      typeof reference.position === "number" &&
      "quote" in reference &&
      typeof reference.quote === "string",
  );
}
