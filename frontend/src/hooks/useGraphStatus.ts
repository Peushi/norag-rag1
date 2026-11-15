import { useCallback, useEffect, useRef, useState } from "react";
import {
  describeRequestError,
  getApiErrorMessage,
  getTraceId,
  isGraphStatus,
  readJson,
  type GraphStatus,
} from "../types/api";
import type { EvaluationDataset } from "../types/evaluations";

const POLL_MS = 1200;

/**
 * The concept graph's state for one corpus, refreshed when documents change
 * and polled while a build runs. `onBuilt` fires once when a build finishes.
 */
export function useGraphStatus(
  dataset: EvaluationDataset,
  documentsVersion: string,
  onBuilt?: () => void,
) {
  const [status, setStatus] = useState<GraphStatus | null>(null);
  const [error, setError] = useState("");
  const [startError, setStartError] = useState<{ message: string; traceId: string | null } | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const wasBuilding = useRef(false);
  const onBuiltRef = useRef(onBuilt);
  onBuiltRef.current = onBuilt;

  const refresh = useCallback(async () => {
    try {
      const response = await fetch(`/api/graphs/${dataset}/status`);
      const data = await readJson(response);
      if (!response.ok || !isGraphStatus(data)) {
        throw new Error(getApiErrorMessage(data, "The concept map’s status couldn’t be loaded."));
      }
      setStatus(data);
      setError("");
      if (wasBuilding.current && !data.building) {
        onBuiltRef.current?.();
      }
      wasBuilding.current = data.building;
    } catch (loadError) {
      setError(describeRequestError(loadError, "The concept map’s status couldn’t be loaded."));
    }
  }, [dataset]);

  useEffect(() => {
    void refresh();
  }, [refresh, documentsVersion]);

  useEffect(() => {
    if (!status?.building) return;
    const timer = window.setInterval(() => void refresh(), POLL_MS);
    return () => window.clearInterval(timer);
  }, [status?.building, refresh]);

  async function startBuild() {
    setIsStarting(true);
    setStartError(null);
    try {
      const response = await fetch(`/api/graphs/${dataset}/build`, { method: "POST" });
      const data = await readJson(response);
      if (!response.ok) {
        setStartError({
          message: getApiErrorMessage(data, "The concept map couldn’t be built."),
          traceId: getTraceId(response, data),
        });
        return;
      }
      wasBuilding.current = true;
      await refresh();
    } catch (requestError) {
      setStartError({
        message: describeRequestError(requestError, "The concept map couldn’t be built."),
        traceId: null,
      });
    } finally {
      setIsStarting(false);
    }
  }

  return { status, error, startError, isStarting, startBuild, refresh };
}
