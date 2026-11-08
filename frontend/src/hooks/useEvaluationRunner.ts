import { useEffect, useState } from "react";
import { getApiErrorMessage } from "../types/api";
import {
  isEvaluationResults,
  isEvaluationRun,
  type EvaluationResults,
  type EvaluationRun,
  type EvaluationRunRequest,
} from "../types/evaluations";

export function useEvaluationRunner() {
  const [run, setRun] = useState<EvaluationRun | null>(null);
  const [results, setResults] = useState<EvaluationResults | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!run || (run.status !== "queued" && run.status !== "running")) {
      return;
    }

    const runId = run.run_id;
    let cancelled = false;
    let timeout: ReturnType<typeof setTimeout>;

    async function refreshRun() {
      try {
        const response = await fetch(`/api/evaluations/${runId}`);
        const data: unknown = await response.json();
        if (!response.ok) {
          throw new Error(
            getApiErrorMessage(data, "Could not check evaluation status."),
          );
        }
        if (!isEvaluationRun(data)) {
          throw new Error("The server returned an invalid evaluation status.");
        }
        if (cancelled) {
          return;
        }

        if (data.status === "completed") {
          const resultsResponse = await fetch(
            `/api/evaluations/${data.run_id}/results`,
          );
          const resultsData: unknown = await resultsResponse.json();
          if (!resultsResponse.ok) {
            throw new Error(
              getApiErrorMessage(
                resultsData,
                "Could not load evaluation results.",
              ),
            );
          }
          if (!isEvaluationResults(resultsData)) {
            throw new Error("The server returned invalid evaluation results.");
          }
          if (!cancelled) {
            setResults(resultsData);
            setRun(data);
          }
        } else if (data.status === "failed") {
          setRun(data);
          setError(data.error || "The evaluation failed.");
        } else {
          setRun(data);
          timeout = setTimeout(() => void refreshRun(), 1500);
        }
      } catch (requestError) {
        if (!cancelled) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Could not check evaluation status.",
          );
        }
      }
    }

    timeout = setTimeout(() => void refreshRun(), 800);
    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  }, [run]);

  async function startEvaluation(request: EvaluationRunRequest) {
    setIsStarting(true);
    setError("");
    setRun(null);
    setResults(null);

    try {
      const response = await fetch("/api/evaluations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      });
      const data: unknown = await response.json();
      if (!response.ok) {
        throw new Error(
          getApiErrorMessage(data, "Could not start the evaluation."),
        );
      }
      if (!isEvaluationRun(data)) {
        throw new Error("The server returned an invalid evaluation run.");
      }
      setRun(data);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not start the evaluation.",
      );
    } finally {
      setIsStarting(false);
    }
  }

  return { run, results, isStarting, error, startEvaluation };
}
