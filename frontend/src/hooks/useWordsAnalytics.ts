import { useState } from "react";
import { getApiErrorMessage } from "../types/api";
import type { EvaluationDataset } from "../types/evaluations";
import {
  isQuestionWordAnalysis,
  isSavedQuestionsResponse,
  isWordChunksResponse,
  isWordVocabularyResponse,
  type QuestionWordAnalysis,
  type SavedQuestion,
  type WordChunksResponse,
  type WordVocabularyResponse,
} from "../types/words";

const PAGE_SIZE = 100;

export function useWordsAnalytics(
  dataset: EvaluationDataset,
  chunkSize: number,
  overlap: number,
) {
  const [vocabulary, setVocabulary] = useState<WordVocabularyResponse | null>(
    null,
  );
  const [wordChunks, setWordChunks] = useState<WordChunksResponse | null>(null);
  const [questionAnalysis, setQuestionAnalysis] =
    useState<QuestionWordAnalysis | null>(null);
  const [questions, setQuestions] = useState<SavedQuestion[]>([]);
  const [isLoadingVocabulary, setIsLoadingVocabulary] = useState(false);
  const [isLoadingChunks, setIsLoadingChunks] = useState(false);
  const [isAnalyzingQuestion, setIsAnalyzingQuestion] = useState(false);
  const [error, setError] = useState("");

  async function loadVocabulary(query = "", offset = 0): Promise<void> {
    setIsLoadingVocabulary(true);
    setError("");
    try {
      const params = new URLSearchParams({
        dataset,
        query,
        limit: String(PAGE_SIZE),
        offset: String(offset),
        chunk_size: String(chunkSize),
        overlap: String(overlap),
      });
      const response = await fetch(`/api/words?${params}`);
      const data: unknown = await response.json();
      if (!response.ok) {
        throw new Error(
          getApiErrorMessage(data, "Could not load corpus vocabulary."),
        );
      }
      if (!isWordVocabularyResponse(data)) {
        throw new Error("The server returned invalid corpus vocabulary.");
      }
      setVocabulary(data);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not load corpus vocabulary.",
      );
    } finally {
      setIsLoadingVocabulary(false);
    }
  }

  async function loadQuestions(): Promise<void> {
    setError("");
    try {
      const response = await fetch(
        `/api/words/questions?dataset=${encodeURIComponent(dataset)}`,
      );
      const data: unknown = await response.json();
      if (!response.ok) {
        throw new Error(getApiErrorMessage(data, "Could not load questions."));
      }
      if (!isSavedQuestionsResponse(data)) {
        throw new Error("The server returned an invalid question list.");
      }
      setQuestions(data.questions);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not load questions.",
      );
    }
  }

  async function loadWordChunks(word: string): Promise<void> {
    setIsLoadingChunks(true);
    setError("");
    try {
      const response = await fetch(
        `/api/words/${encodeURIComponent(word)}/chunks?${new URLSearchParams({
          dataset,
          chunk_size: String(chunkSize),
          overlap: String(overlap),
        })}`,
      );
      const data: unknown = await response.json();
      if (!response.ok) {
        throw new Error(getApiErrorMessage(data, "Could not load matching chunks."));
      }
      if (!isWordChunksResponse(data)) {
        throw new Error("The server returned invalid word matches.");
      }
      setWordChunks(data);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not load matching chunks.",
      );
    } finally {
      setIsLoadingChunks(false);
    }
  }

  async function analyzeQuestion(question: string): Promise<void> {
    setIsAnalyzingQuestion(true);
    setError("");
    try {
      const response = await fetch("/api/words/analyze-question", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dataset,
          question,
          chunk_size: chunkSize,
          overlap,
        }),
      });
      const data: unknown = await response.json();
      if (!response.ok) {
        throw new Error(
          getApiErrorMessage(data, "Could not analyze question words."),
        );
      }
      if (!isQuestionWordAnalysis(data)) {
        throw new Error("The server returned an invalid question analysis.");
      }
      setQuestionAnalysis(data);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not analyze question words.",
      );
    } finally {
      setIsAnalyzingQuestion(false);
    }
  }

  function clearResults() {
    setWordChunks(null);
    setQuestionAnalysis(null);
  }

  return {
    vocabulary,
    wordChunks,
    questionAnalysis,
    questions,
    isLoadingVocabulary,
    isLoadingChunks,
    isAnalyzingQuestion,
    error,
    loadVocabulary,
    loadQuestions,
    loadWordChunks,
    analyzeQuestion,
    clearResults,
  };
}
