import { useState } from "react";
import { DEFAULT_ANSWER_STYLE, type AnswerStyle } from "../types/api";

const STORAGE_KEY = "bakefix.answerStyle";

const ALLOWED: { [K in keyof AnswerStyle]: readonly AnswerStyle[K][] } = {
  level: ["beginner", "expert"],
  tone: ["friendly", "professional", "technical"],
  length: ["short", "medium", "long"],
  eli12: [true, false],
};

/** Read a saved style, keeping only values the backend accepts. */
function loadSavedStyle(): AnswerStyle {
  try {
    const saved: unknown = JSON.parse(
      window.localStorage.getItem(STORAGE_KEY) ?? "null",
    );
    if (typeof saved !== "object" || saved === null) {
      return DEFAULT_ANSWER_STYLE;
    }
    const record = saved as Record<string, unknown>;
    const style = { ...DEFAULT_ANSWER_STYLE };
    for (const key of Object.keys(ALLOWED) as (keyof AnswerStyle)[]) {
      if ((ALLOWED[key] as readonly unknown[]).includes(record[key])) {
        (style as Record<string, unknown>)[key] = record[key];
      }
    }
    return style;
  } catch {
    return DEFAULT_ANSWER_STYLE;
  }
}

/** The reader's preferred answer style, remembered in this browser only. */
export function useAnswerStyle() {
  const [style, setStyle] = useState<AnswerStyle>(loadSavedStyle);

  function updateStyle(change: Partial<AnswerStyle>) {
    setStyle((current) => {
      const next = { ...current, ...change };
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        // Storage can be unavailable (private mode); the choice still applies.
      }
      return next;
    });
  }

  function resetStyle() {
    updateStyle(DEFAULT_ANSWER_STYLE);
  }

  return { style, updateStyle, resetStyle };
}
