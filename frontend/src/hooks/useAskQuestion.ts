import { useState, type KeyboardEvent } from "react";
import {
  getApiErrorDetail,
  isAskResponse,
  readJson,
  toGlossary,
  type AnswerStyle,
  type Answer,
  type RetrieverName,
} from "../types/api";

const EMPTY_ANSWER: Answer = {
  kind: "empty",
  text: "Your answer will feel right at home here.",
};

type UseAskQuestionOptions = {
  documentCount: number;
  selectedDocumentIds: string[] | null;
  topK: number;
  dataset: "baking" | "kestrel";
  retrievers: RetrieverName[];
  includePathContext: boolean;
  style: AnswerStyle;
};

export function useAskQuestion({
  documentCount,
  selectedDocumentIds,
  topK,
  dataset,
  retrievers,
  includePathContext,
  style,
}: UseAskQuestionOptions) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer>(EMPTY_ANSWER);
  const [status, setStatus] = useState("");

  async function askQuestion(): Promise<void> {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) {
      setStatus("Write a question first, and we’ll take it from there.");
      return;
    }

    if (documentCount === 0) {
      setStatus(
        "There are no documents to search yet. Add a recipe, note or manual first.",
      );
      return;
    }

    if (retrievers.length === 0) {
      setStatus("Open “Search options” and turn on at least one search method.");
      return;
    }

    if (
      dataset === "baking" &&
      selectedDocumentIds !== null &&
      selectedDocumentIds.length === 0
    ) {
      setStatus("Open “Search options” and choose at least one document to search.");
      return;
    }

    setStatus("");
    setAnswer({ kind: "loading" });
    // Remember the style this answer was requested in, even if the reader
    // changes the controls while waiting.
    const requestStyle: AnswerStyle = style.eli12
      ? { ...style, level: "beginner" }
      : style;

    let traceId: string | null = null;
    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: trimmedQuestion,
          dataset,
          document_ids: dataset === "baking" ? selectedDocumentIds : null,
          top_k: topK,
          retrievers,
          include_path_context: includePathContext,
          style: requestStyle,
        }),
      });
      traceId = response.headers.get("x-trace-id");
      const data = await readJson(response);

      if (!response.ok) {
        const failure = describeAskFailure(data);
        setAnswer({ kind: "error", ...failure, trace_id: traceId });
        return;
      }

      if (!isAskResponse(data)) {
        setAnswer({
          kind: "error",
          text: "BakeFix received an answer it couldn’t read. Please try again.",
          retryable: true,
          trace_id: traceId,
        });
        return;
      }

      if (data.status === "not_found") {
        setAnswer({
          kind: "not_found",
          text: data.answer,
          style: requestStyle,
          retrieval: data.retrieval,
          trace_id: data.trace_id ?? traceId,
        });
      } else {
        setAnswer({
          kind: "answered",
          text: data.answer,
          style: requestStyle,
          references: data.references,
          glossary: toGlossary(data.glossary),
          retrieval: data.retrieval,
          trace_id: data.trace_id ?? traceId,
        });
      }
    } catch {
      // fetch only throws when the server cannot be reached at all.
      setAnswer({
        kind: "error",
        text: "BakeFix can’t reach its server. Make sure the backend is running, then try again.",
        retryable: true,
        trace_id: traceId,
      });
    }
  }

  function handleQuestionKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      void askQuestion();
    }
  }

  return {
    question,
    setQuestion,
    answer,
    status,
    askQuestion,
    handleQuestionKeyDown,
  };
}

/** Turn an API error into a message a non-programmer can act on. */
function describeAskFailure(data: unknown): { text: string; retryable: boolean } {
  const detail = getApiErrorDetail(data);
  switch (detail?.code) {
    case "LLM_UNAVAILABLE":
      if (detail.message.includes("GOOGLE_API_KEY")) {
        return {
          text: "BakeFix isn’t set up to write answers yet: add your GOOGLE_API_KEY to the .env file (see the README), then restart the server.",
          retryable: false,
        };
      }
      return {
        text: "The answer service isn’t available right now. Check your internet connection and try again in a moment.",
        retryable: true,
      };
    case "LLM_TIMEOUT":
      return { text: "The answer took too long to arrive. Please try again.", retryable: true };
    case "LLM_INVALID_RESPONSE":
      return {
        text: "BakeFix couldn’t check this answer against your documents, so it didn’t show it. Try again, or rephrase your question.",
        retryable: true,
      };
    case "LLM_UPSTREAM_ERROR":
      return {
        text: "The answer service returned an error. Please try again in a moment.",
        retryable: detail.retryable,
      };
    case "VALIDATION_ERROR":
      return {
        text: "That question couldn’t be sent. Check that it isn’t empty, then try again.",
        retryable: false,
      };
    case "INDEXING_ERROR":
      return {
        text: "Your documents couldn’t be prepared for search. Please try again.",
        retryable: true,
      };
    default:
      return {
        text: detail?.message ?? "Something went wrong. Please try again.",
        retryable: detail?.retryable ?? true,
      };
  }
}
