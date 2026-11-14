import { useState } from "react";
import {
  getApiErrorMessage,
  getTraceId,
  isQuarantineItem,
  readJson,
  type IndexingActivity,
  type QuarantineItem,
} from "../types/api";

/** Documents held by the injection scanner, and the review actions on them. */
export function useQuarantine() {
  const [items, setItems] = useState<QuarantineItem[]>([]);
  const [loadError, setLoadError] = useState("");

  async function loadQuarantine(): Promise<void> {
    try {
      const response = await fetch("/api/quarantine");
      const data = await readJson(response);
      if (!response.ok) {
        throw new Error(
          getApiErrorMessage(data, "Documents held for review couldn’t be loaded."),
        );
      }
      const rows =
        typeof data === "object" && data !== null && "items" in data
          ? data.items
          : null;
      if (!Array.isArray(rows) || !rows.every(isQuarantineItem)) {
        throw new Error("The server returned an unexpected review list.");
      }
      setItems(rows);
      setLoadError("");
    } catch (error) {
      setLoadError(
        error instanceof Error
          ? error.message
          : "Documents held for review couldn’t be loaded.",
      );
    }
  }

  async function review(
    item: QuarantineItem,
    action: "release" | "reject",
  ): Promise<IndexingActivity> {
    let traceId: string | null = null;
    try {
      const response = await fetch(
        `/api/quarantine/${encodeURIComponent(item.id)}/${action}`,
        action === "release"
          ? {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ approved: true }),
            }
          : { method: "POST" },
      );
      const data = await readJson(response);
      traceId = getTraceId(response, data);
      if (!response.ok) {
        throw new Error(
          getApiErrorMessage(
            data,
            action === "release"
              ? `“${item.source}” couldn’t be added.`
              : `“${item.source}” couldn’t be discarded.`,
          ),
        );
      }
      return {
        message:
          action === "release"
            ? `“${item.source}” was reviewed and is now searchable.`
            : `“${item.source}” was discarded. Its text has been deleted.`,
        tone: "success",
        traceId,
      };
    } catch (error) {
      return {
        message:
          error instanceof Error ? error.message : "The review couldn’t be saved.",
        tone: "error",
        traceId,
      };
    } finally {
      await loadQuarantine();
    }
  }

  return {
    heldItems: items,
    quarantineLoadError: loadError,
    loadQuarantine,
    releaseItem: (item: QuarantineItem) => review(item, "release"),
    rejectItem: (item: QuarantineItem) => review(item, "reject"),
  };
}
