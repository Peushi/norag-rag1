import type { EvaluationDataset } from "./evaluations";

export type CorpusWord = {
  word: string;
  occurrence_count: number;
  chunk_count: number;
};

export type WordChunkMatch = {
  chunk_id: string;
  source: string;
  position: number;
  text: string;
  occurrence_count: number;
  matched_words: string[];
};

export type WordVocabularyResponse = {
  dataset: EvaluationDataset;
  chunk_size: number;
  overlap: number;
  total_words: number;
  matching_words: number;
  offset: number;
  words: CorpusWord[];
};

export type WordChunksResponse = {
  dataset: EvaluationDataset;
  chunk_size: number;
  overlap: number;
  word: string;
  occurrence_count: number;
  chunk_count: number;
  chunks: WordChunkMatch[];
};

export type QuestionWordAnalysis = {
  dataset: EvaluationDataset;
  chunk_size: number;
  overlap: number;
  words_found: CorpusWord[];
  words_missing: string[];
  matching_chunks: WordChunkMatch[];
};

export type SavedQuestion = {
  id: string;
  question: string;
  type: string;
};

export type SavedQuestionsResponse = {
  dataset: EvaluationDataset;
  questions: SavedQuestion[];
};

export function isWordVocabularyResponse(
  value: unknown,
): value is WordVocabularyResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    "dataset" in value &&
    (value.dataset === "baking" || value.dataset === "kestrel") &&
    "chunk_size" in value &&
    typeof value.chunk_size === "number" &&
    "overlap" in value &&
    typeof value.overlap === "number" &&
    "total_words" in value &&
    typeof value.total_words === "number" &&
    "matching_words" in value &&
    typeof value.matching_words === "number" &&
    "offset" in value &&
    typeof value.offset === "number" &&
    "words" in value &&
    Array.isArray(value.words) &&
    value.words.every(isCorpusWord)
  );
}

export function isWordChunksResponse(value: unknown): value is WordChunksResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    "dataset" in value &&
    (value.dataset === "baking" || value.dataset === "kestrel") &&
    "chunk_size" in value &&
    typeof value.chunk_size === "number" &&
    "overlap" in value &&
    typeof value.overlap === "number" &&
    "word" in value &&
    typeof value.word === "string" &&
    "occurrence_count" in value &&
    typeof value.occurrence_count === "number" &&
    "chunk_count" in value &&
    typeof value.chunk_count === "number" &&
    "chunks" in value &&
    Array.isArray(value.chunks) &&
    value.chunks.every(isWordChunkMatch)
  );
}

export function isQuestionWordAnalysis(
  value: unknown,
): value is QuestionWordAnalysis {
  return (
    typeof value === "object" &&
    value !== null &&
    "dataset" in value &&
    (value.dataset === "baking" || value.dataset === "kestrel") &&
    "chunk_size" in value &&
    typeof value.chunk_size === "number" &&
    "overlap" in value &&
    typeof value.overlap === "number" &&
    "words_found" in value &&
    Array.isArray(value.words_found) &&
    value.words_found.every(isCorpusWord) &&
    "words_missing" in value &&
    Array.isArray(value.words_missing) &&
    value.words_missing.every((word: unknown) => typeof word === "string") &&
    "matching_chunks" in value &&
    Array.isArray(value.matching_chunks) &&
    value.matching_chunks.every(isWordChunkMatch)
  );
}

export function isSavedQuestionsResponse(
  value: unknown,
): value is SavedQuestionsResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    "dataset" in value &&
    (value.dataset === "baking" || value.dataset === "kestrel") &&
    "questions" in value &&
    Array.isArray(value.questions) &&
    value.questions.every(
      (question: unknown) =>
        typeof question === "object" &&
        question !== null &&
        "id" in question &&
        typeof question.id === "string" &&
        "question" in question &&
        typeof question.question === "string" &&
        "type" in question &&
        typeof question.type === "string",
    )
  );
}

function isCorpusWord(value: unknown): value is CorpusWord {
  return (
    typeof value === "object" &&
    value !== null &&
    "word" in value &&
    typeof value.word === "string" &&
    "occurrence_count" in value &&
    typeof value.occurrence_count === "number" &&
    "chunk_count" in value &&
    typeof value.chunk_count === "number"
  );
}

function isWordChunkMatch(value: unknown): value is WordChunkMatch {
  return (
    typeof value === "object" &&
    value !== null &&
    "chunk_id" in value &&
    typeof value.chunk_id === "string" &&
    "source" in value &&
    typeof value.source === "string" &&
    "position" in value &&
    typeof value.position === "number" &&
    "text" in value &&
    typeof value.text === "string" &&
    "occurrence_count" in value &&
    typeof value.occurrence_count === "number" &&
    "matched_words" in value &&
    Array.isArray(value.matched_words) &&
    value.matched_words.every((word: unknown) => typeof word === "string")
  );
}
