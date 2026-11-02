import { useState, type KeyboardEvent } from "react";
import { getApiErrorMessage, isAskResponse, type Answer } from "../types/api";

const EMPTY_ANSWER: Answer = {
  kind: "empty",
  text: "Your answer will feel right at home here.",
};

type UseAskQuestionOptions = {
  documentCount: number;
  selectedDocumentIds: string[] | null;
  topK: number;
};

export function useAskQuestion({
  documentCount,
  selectedDocumentIds,
  topK,
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

    if (selectedDocumentIds !== null && selectedDocumentIds.length === 0) {
      setStatus("Select at least one document to search.");
      return;
    }

    setStatus("Looking through your notes...");
    setAnswer({ kind: "loading" });

    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: trimmedQuestion,
          document_ids: selectedDocumentIds,
          top_k: topK,
        }),
      });
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
        setAnswer({ kind: "not_found", text: data.answer });
        setStatus("No matching note found.");
      } else {
        setAnswer({
          kind: "answered",
          text: data.answer,
          references: data.references,
        });
        setStatus("Here’s what I found.");
      }
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Something went wrong. Please try again.";
      setAnswer({ kind: "error", text: message });
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
