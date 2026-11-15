import { useEffect, useRef, useState, type CSSProperties } from "react";
import type { AnswerReference } from "../types/api";
import { documentTitle } from "../utils/documentNames";

const FEEDBACK_KEY = "bakefix.feedback";
const MAX_FEEDBACK_ENTRIES = 200;
const SPRINKLE_COLOURS = ["#b85e43", "#e3a857", "#78846a", "#d98c8c", "#f2d16b", "#8fb3c9"];

type Feedback = "helpful" | "not_helpful";

function prefersReducedMotion(): boolean {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

/** The answer and its numbered sources as plain text, ready to paste. */
function answerAsText(text: string, references: AnswerReference[]): string {
  if (references.length === 0) {
    return text;
  }
  const sources = references
    .map((reference, index) => `[${index + 1}] ${documentTitle(reference.source)}`)
    .join("\n");
  return `${text}\n\nSources:\n${sources}`;
}

/** Feedback is kept in this browser only (per answer trace), as a personal record. */
function readFeedback(traceId: string | null | undefined): Feedback | null {
  if (!traceId) return null;
  try {
    const saved = JSON.parse(localStorage.getItem(FEEDBACK_KEY) ?? "{}");
    const value = saved?.[traceId]?.value;
    return value === "helpful" || value === "not_helpful" ? value : null;
  } catch {
    return null;
  }
}

function saveFeedback(traceId: string, value: Feedback) {
  try {
    const saved = JSON.parse(localStorage.getItem(FEEDBACK_KEY) ?? "{}") ?? {};
    saved[traceId] = { value, at: new Date().toISOString() };
    const newest = Object.entries(saved)
      .sort(([, a], [, b]) => String((b as { at: string }).at).localeCompare(String((a as { at: string }).at)))
      .slice(0, MAX_FEEDBACK_ENTRIES);
    localStorage.setItem(FEEDBACK_KEY, JSON.stringify(Object.fromEntries(newest)));
  } catch {
    // Storage can be unavailable (private window); feedback still shows its thanks.
  }
}

type Sprinkle = { id: number; dx: number; dy: number; rotate: number; colour: string; delay: number };

function makeSprinkles(): Sprinkle[] {
  return Array.from({ length: 16 }, (_, id) => {
    const angle = (Math.PI * 2 * id) / 16 + Math.random() * 0.4;
    const distance = 34 + Math.random() * 30;
    return {
      id,
      dx: Math.cos(angle) * distance,
      dy: Math.sin(angle) * distance - 14,
      rotate: Math.random() * 360,
      colour: SPRINKLE_COLOURS[id % SPRINKLE_COLOURS.length],
      delay: Math.random() * 60,
    };
  });
}

type AnswerActionsProps = {
  text: string;
  references: AnswerReference[];
  traceId?: string | null;
};

/** "Copy answer" and "Was this helpful?" under an answer. */
export function AnswerActions({ text, references, traceId }: AnswerActionsProps) {
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  const [feedback, setFeedback] = useState<Feedback | null>(() => readFeedback(traceId));
  const [sprinkles, setSprinkles] = useState<Sprinkle[]>([]);
  const timers = useRef<number[]>([]);

  useEffect(() => () => timers.current.forEach((timer) => window.clearTimeout(timer)), []);

  function later(callback: () => void, ms: number) {
    timers.current.push(window.setTimeout(callback, ms));
  }

  async function copyAnswer() {
    try {
      await navigator.clipboard.writeText(answerAsText(text, references));
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
    later(() => setCopyState("idle"), 2000);
  }

  function giveFeedback(value: Feedback) {
    setFeedback(value);
    if (traceId) saveFeedback(traceId, value);
    if (value === "helpful" && !prefersReducedMotion()) {
      setSprinkles(makeSprinkles());
      later(() => setSprinkles([]), 1000);
    }
  }

  return (
    <div className="answer-actions">
      <button
        type="button"
        className={`copy-answer ${copyState}`}
        onClick={() => void copyAnswer()}
      >
        <span className="copy-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" className="icon-clipboard">
            <rect x="7" y="5" width="11" height="14" rx="2" />
            <path d="M10 5V4a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v1" />
          </svg>
          <svg viewBox="0 0 24 24" className="icon-check">
            <path d="M5 12.5l4.5 4.5L19 7.5" />
          </svg>
        </span>
        <span aria-live="polite">
          {copyState === "copied" ? "Copied!" : copyState === "failed" ? "Couldn’t copy" : "Copy answer"}
        </span>
      </button>

      <div className="answer-feedback" role="group" aria-label="Was this answer helpful?">
        {feedback ? (
          <p className="feedback-thanks" aria-live="polite">
            {feedback === "helpful" ? "Thanks! Glad it helped." : "Thanks, that helps us improve."}
          </p>
        ) : (
          <>
            <span className="feedback-question">Was this helpful?</span>
            <span className="feedback-buttons">
              <button
                type="button"
                className="feedback-button"
                aria-label="Yes, helpful"
                onClick={() => giveFeedback("helpful")}
              >
                👍
              </button>
              <button
                type="button"
                className="feedback-button"
                aria-label="No, not helpful"
                onClick={() => giveFeedback("not_helpful")}
              >
                👎
              </button>
            </span>
          </>
        )}
        {sprinkles.length > 0 && (
          <span className="sprinkles" aria-hidden="true">
            {sprinkles.map((sprinkle) => (
              <span
                key={sprinkle.id}
                className="sprinkle"
                style={{
                  "--dx": `${sprinkle.dx}px`,
                  "--dy": `${sprinkle.dy}px`,
                  "--rot": `${sprinkle.rotate}deg`,
                  background: sprinkle.colour,
                  animationDelay: `${sprinkle.delay}ms`,
                } as CSSProperties}
              />
            ))}
          </span>
        )}
      </div>
    </div>
  );
}
