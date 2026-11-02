export type EvaluationDataset = "baking" | "kestrel";

export type EvaluationRunRequest = {
  dataset: EvaluationDataset;
  top_k: number;
  chunk_size: number;
  overlap: number;
  max_distance: number | null;
  limit: number | null;
};

export type EvaluationRun = EvaluationRunRequest & {
  run_id: string;
  status: "queued" | "running" | "completed" | "failed";
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
};

export type EvaluationResult = {
  id: string;
  question: string;
  answerable?: boolean;
  retrieval_hit?: boolean | null;
  status?: string;
  model_answer?: string | null;
  error?: string | null;
  manual_review?: string | { grade?: string; reason?: string };
};

export type EvaluationResults = {
  run_id: string;
  dataset: EvaluationDataset;
  results: EvaluationResult[];
};

export function isEvaluationRun(value: unknown): value is EvaluationRun {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  return (
    "run_id" in value &&
    typeof value.run_id === "string" &&
    "dataset" in value &&
    (value.dataset === "baking" || value.dataset === "kestrel") &&
    "status" in value &&
    ["queued", "running", "completed", "failed"].includes(
      String(value.status),
    ) &&
    "top_k" in value &&
    typeof value.top_k === "number" &&
    "chunk_size" in value &&
    typeof value.chunk_size === "number" &&
    "overlap" in value &&
    typeof value.overlap === "number"
  );
}

function isEvaluationResult(value: unknown): value is EvaluationResult {
  return (
    typeof value === "object" &&
    value !== null &&
    "id" in value &&
    typeof value.id === "string" &&
    "question" in value &&
    typeof value.question === "string"
  );
}

export function isEvaluationResults(value: unknown): value is EvaluationResults {
  return (
    typeof value === "object" &&
    value !== null &&
    "run_id" in value &&
    typeof value.run_id === "string" &&
    "dataset" in value &&
    (value.dataset === "baking" || value.dataset === "kestrel") &&
    "results" in value &&
    Array.isArray(value.results) &&
    value.results.every(isEvaluationResult)
  );
}
