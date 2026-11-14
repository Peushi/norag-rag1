import { useState } from "react";
import type { TraceDetail, TraceSpan } from "../types/api";
import { getApiErrorMessage, isTraceDetail } from "../types/api";
import "../../styles/retriever-controls.css";

type TraceDetailsProps = {
  traceId?: string | null;
};

const OPERATION_LABELS: Record<TraceDetail["operation"], string> = {
  question: "Question",
  indexing: "Indexing run",
};

/** A "Details" toggle that loads and shows one stored trace on demand. */
export function TraceDetails({ traceId }: TraceDetailsProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [trace, setTrace] = useState<TraceDetail | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!traceId) {
    return null;
  }
  const activeTraceId = traceId;

  async function toggleDetails() {
    if (isOpen) {
      setIsOpen(false);
      return;
    }

    setIsOpen(true);
    setError(null);
    if (trace?.trace_id === activeTraceId) {
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(
        `/api/traces/${encodeURIComponent(activeTraceId)}`,
      );
      const data: unknown = await response.json();
      if (!response.ok) {
        throw new Error(
          getApiErrorMessage(data, "Could not load this trace."),
        );
      }
      if (!isTraceDetail(data)) {
        throw new Error("The server returned an invalid trace.");
      }
      setTrace(data);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Could not load this trace.",
      );
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <section className="trace-details">
      <button
        className="trace-details-toggle"
        type="button"
        aria-expanded={isOpen}
        onClick={() => void toggleDetails()}
      >
        {isOpen ? "Hide trace" : "Details"}
      </button>
      {isOpen && (
        <div className="trace-details-content" aria-live="polite">
          {isLoading && <p>Loading trace…</p>}
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          {trace && !isLoading && (
            <>
              <p>
                {OPERATION_LABELS[trace.operation]} · {trace.status}
                {trace.outcome ? ` · ${trace.outcome}` : ""} · trace{" "}
                {trace.trace_id}
              </p>
              <ol className="trace-span-list">
                {trace.spans.map((span, index) => (
                  <TraceSpanItem span={span} key={`${span.name}-${index}`} />
                ))}
              </ol>
            </>
          )}
        </div>
      )}
    </section>
  );
}

type TraceAttributeValue = TraceSpan["attributes"][string];

type TraceResult = {
  rank: number;
  fields: Record<string, TraceAttributeValue>;
};

const RESULT_ATTRIBUTE = /^result\.(\d+)\.([a-z_]+)$/;

/** Show decimals without floating-point noise (0.00047000000000000004 → 0.00047). */
function formatAttribute(value: TraceAttributeValue): string {
  if (typeof value === "number" && !Number.isInteger(value)) {
    return String(Number(value.toPrecision(6)));
  }
  return String(value);
}

/** Split flat span attributes into plain metadata and ranked retrieval results. */
function splitTraceAttributes(attributes: TraceSpan["attributes"]) {
  const plain: [string, TraceAttributeValue][] = [];
  const resultsByRank = new Map<number, TraceResult>();

  for (const [key, value] of Object.entries(attributes)) {
    const match = RESULT_ATTRIBUTE.exec(key);
    if (!match) {
      plain.push([key, value]);
      continue;
    }
    const rank = Number(match[1]);
    const result = resultsByRank.get(rank) ?? { rank, fields: {} };
    result.fields[match[2]] = value;
    resultsByRank.set(rank, result);
  }

  const results = [...resultsByRank.values()].sort((a, b) => a.rank - b.rank);
  return { plain, results };
}

function TraceSpanItem({ span }: { span: TraceSpan }) {
  const { plain, results } = splitTraceAttributes(span.attributes);

  return (
    <li>
      <strong>{span.name}</strong>
      <span>
        {span.status} · {span.duration_ms.toFixed(1)} ms
      </span>
      {plain.length > 0 && (
        <dl>
          {plain.map(([key, value]) => (
            <div key={key}>
              <dt>{key}</dt>
              <dd>{formatAttribute(value)}</dd>
            </div>
          ))}
        </dl>
      )}
      {results.length > 0 && (
        <ol className="trace-result-list" aria-label="Retrieved passages">
          {results.map(({ rank, fields }) => (
            <li key={rank}>
              <span className="trace-result-rank">#{rank}</span>
              <span>
                {String(fields.source ?? "unknown source")}
                {typeof fields.position === "number"
                  ? ` · chunk ${fields.position + 1}`
                  : ""}
                {typeof fields.score === "number"
                  ? ` · score ${fields.score.toFixed(4)}`
                  : ""}
              </span>
              {fields.found_by !== undefined && (
                <span className="trace-result-meta">
                  Found by {String(fields.found_by)}
                </span>
              )}
              {fields.chunk_id !== undefined && (
                <span className="trace-result-meta">
                  {String(fields.chunk_id)}
                </span>
              )}
            </li>
          ))}
        </ol>
      )}
      {span.error_type && (
        <span className="error">Failed: {span.error_type}</span>
      )}
    </li>
  );
}
