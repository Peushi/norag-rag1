import type { EvaluationDataset } from "./evaluations";

export type RetrievalMetricValues = {
  hit_rate: number | null;
  recall: number | null;
};

export type RetrievalMetricSummary = {
  answerable_questions: number;
  excluded_questions: number;
  metrics: Record<string, RetrievalMetricValues>;
};

export type RetrievalEvidenceChunk = {
  id: string;
  rank: number;
};

export type RetrievalEvidence = {
  source: string;
  quote: string;
  boundary_split: boolean;
  matched_chunks: RetrievalEvidenceChunk[];
};

export type RetrievalPassage = {
  id: string;
  rank: number;
  text: string;
  source: string;
  position: number;
  distance: number;
  relevant: boolean;
  matched_evidence_quotes: string[];
};

export type RetrievalQuestionMetric = {
  hit: boolean;
  recall: number;
  matched_evidence: number;
  expected_evidence: number;
};

export type RetrievalQuestionResult = {
  id: string;
  question: string;
  type: string;
  answerable: boolean;
  evidence: RetrievalEvidence[];
  retrieval_metrics: Record<string, RetrievalQuestionMetric> | null;
  evaluation_chunks: RetrievalPassage[];
};

export type RetrievalConfigurationResult = {
  config_id: string;
  chunk_size: number;
  overlap: number;
  top_k: number;
  max_distance: number | null;
  limit: number | null;
  generate_answers: boolean;
  top_k_values: number[];
  answerable_questions: number;
  excluded_questions: number;
  metrics: Record<string, RetrievalMetricValues>;
  question_type_breakdown: Record<string, RetrievalMetricSummary>;
  questions: RetrievalQuestionResult[];
};

export type RetrievalComparison = {
  experiment_id: string;
  dataset: EvaluationDataset;
  embedding_model: string;
  distance_metric: string;
  relevance_rule: string;
  recall_averaging: string;
  configurations: RetrievalConfigurationResult[];
};

export function isRetrievalComparison(
  value: unknown,
): value is RetrievalComparison {
  return (
    isRecord(value) &&
    typeof value.experiment_id === "string" &&
    isDataset(value.dataset) &&
    typeof value.embedding_model === "string" &&
    typeof value.distance_metric === "string" &&
    typeof value.relevance_rule === "string" &&
    typeof value.recall_averaging === "string" &&
    Array.isArray(value.configurations) &&
    value.configurations.every(isConfiguration)
  );
}

function isConfiguration(value: unknown): value is RetrievalConfigurationResult {
  return (
    isRecord(value) &&
    typeof value.config_id === "string" &&
    typeof value.chunk_size === "number" &&
    typeof value.overlap === "number" &&
    typeof value.top_k === "number" &&
    isNullableNumber(value.max_distance) &&
    (value.limit === null || typeof value.limit === "number") &&
    typeof value.generate_answers === "boolean" &&
    isNumberArray(value.top_k_values) &&
    typeof value.answerable_questions === "number" &&
    typeof value.excluded_questions === "number" &&
    isMetricMap(value.metrics) &&
    isRecord(value.question_type_breakdown) &&
    Object.values(value.question_type_breakdown).every(isMetricSummary) &&
    Array.isArray(value.questions) &&
    value.questions.every(isQuestion)
  );
}

function isMetricSummary(value: unknown): value is RetrievalMetricSummary {
  return (
    isRecord(value) &&
    typeof value.answerable_questions === "number" &&
    typeof value.excluded_questions === "number" &&
    isMetricMap(value.metrics)
  );
}

function isMetricMap(value: unknown): value is Record<string, RetrievalMetricValues> {
  return (
    isRecord(value) &&
    Object.values(value).every(
      (metric) =>
        isRecord(metric) &&
        isNullableNumber(metric.hit_rate) &&
        isNullableNumber(metric.recall),
    )
  );
}

function isQuestion(value: unknown): value is RetrievalQuestionResult {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.question === "string" &&
    typeof value.type === "string" &&
    typeof value.answerable === "boolean" &&
    Array.isArray(value.evidence) &&
    value.evidence.every(isEvidence) &&
    (value.retrieval_metrics === null || isQuestionMetricMap(value.retrieval_metrics)) &&
    Array.isArray(value.evaluation_chunks) &&
    value.evaluation_chunks.every(isPassage)
  );
}

function isQuestionMetricMap(
  value: unknown,
): value is Record<string, RetrievalQuestionMetric> {
  return (
    isRecord(value) &&
    Object.values(value).every(
      (metric) =>
        isRecord(metric) &&
        typeof metric.hit === "boolean" &&
        typeof metric.recall === "number" &&
        typeof metric.matched_evidence === "number" &&
        typeof metric.expected_evidence === "number",
    )
  );
}

function isEvidence(value: unknown): value is RetrievalEvidence {
  return (
    isRecord(value) &&
    typeof value.source === "string" &&
    typeof value.quote === "string" &&
    typeof value.boundary_split === "boolean" &&
    Array.isArray(value.matched_chunks) &&
    value.matched_chunks.every(
      (chunk) =>
        isRecord(chunk) &&
        typeof chunk.id === "string" &&
        typeof chunk.rank === "number",
    )
  );
}

function isPassage(value: unknown): value is RetrievalPassage {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.rank === "number" &&
    typeof value.text === "string" &&
    typeof value.source === "string" &&
    typeof value.position === "number" &&
    typeof value.distance === "number" &&
    typeof value.relevant === "boolean" &&
    Array.isArray(value.matched_evidence_quotes) &&
    value.matched_evidence_quotes.every((quote) => typeof quote === "string")
  );
}

function isDataset(value: unknown): value is EvaluationDataset {
  return value === "baking" || value === "kestrel";
}

function isNumberArray(value: unknown): value is number[] {
  return Array.isArray(value) && value.every((item) => typeof item === "number");
}

function isNullableNumber(value: unknown): value is number | null {
  return value === null || typeof value === "number";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
