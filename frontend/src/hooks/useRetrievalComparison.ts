import { useEffect, useState } from "react";
import { getApiErrorMessage } from "../types/api";
import type { EvaluationDataset } from "../types/evaluations";
import {
  isRetrievalComparison,
  type RetrievalComparison,
} from "../types/retrievalComparisons";

const EXPERIMENT_IDS: Record<EvaluationDataset, string> = {
  baking: "retrieval-v2-baking",
  kestrel: "retrieval-v2-kestrel",
};

export function useRetrievalComparison(dataset: EvaluationDataset) {
  const [comparison, setComparison] = useState<RetrievalComparison | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function loadComparison() {
      setIsLoading(true);
      setError("");
      setComparison(null);
      try {
        const experimentId = EXPERIMENT_IDS[dataset];
        const response = await fetch(
          `/api/evaluations/retrieval/${experimentId}/results`,
          { signal: controller.signal },
        );
        const data: unknown = await response.json();
        if (!response.ok) {
          throw new Error(
            getApiErrorMessage(data, "Could not load retrieval comparison."),
          );
        }
        if (!isRetrievalComparison(data)) {
          throw new Error("The server returned an invalid retrieval comparison.");
        }
        setComparison(data);
      } catch (requestError) {
        if (controller.signal.aborted) {
          return;
        }
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Could not load retrieval comparison.",
        );
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    }

    void loadComparison();
    return () => controller.abort();
  }, [dataset]);

  return { comparison, isLoading, error };
}
