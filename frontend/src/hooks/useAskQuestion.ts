import { useState, type KeyboardEvent } from "react";
import {
  getApiErrorMessage,
  isAskResponse,
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
};

export function useAskQuestion({
  documentCount,
  selectedDocumentIds,
  topK,
  dataset,
  retrievers,
  includePathContext,
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
      setStatus("There are no documents to search. Add a document first.");
      return;
    }

    if (retrievers.length === 0) {
      setStatus("Select at least one retrieval method.");
      return;
    }

    if (
      dataset === "baking" &&
      selectedDocumentIds !== null &&
      selectedDocumentIds.length === 0
    ) {
      setStatus("Select at least one document to search.");
      return;
    }

    setStatus("Looking through your notes...");
    setAnswer({ kind: "loading" });

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
        }),
      });
      traceId = response.headers.get("x-trace-id");
      const data: unknown = await response.json();

      if (!response.ok) {
        throw new Error(
          getApiErrorMessage(data, "Something went wrong. Please try again."),
        );
      }

      if (!isAskResponse(data)) {
        throw new Error("The server returned an invalid answer.");
      }

      if (data.status === "not_found") {
        setAnswer({
          kind: "not_found",
          text: data.answer,
          retrieval: data.retrieval,
          trace_id: data.trace_id ?? traceId,
        });
        setStatus("No matching note found.");
      } else {
        setAnswer({
          kind: "answered",
          text: data.answer,
          references: data.references,
          retrieval: data.retrieval,
          trace_id: data.trace_id ?? traceId,
        });
        setStatus("Here’s what I found.");
      }
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Something went wrong. Please try again.";
      setAnswer({ kind: "error", text: message, trace_id: traceId });
      setStatus("We couldn’t find an answer just now.");
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
