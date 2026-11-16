import { useCallback, useEffect, useState } from "react";
import { describeRequestError, getApiErrorMessage, readJson } from "../types/api";
import "../../styles/metrics.css";

type Latency = { count: number; p50_ms: number | null; p95_ms: number | null };
type StepLatency = Latency & { step: string };

type Metrics = {
  window_days: number;
  generated_at: string;
  trace_count: number;
  questions: {
    total: number;
    outcomes: Record<"answered" | "abstained" | "invalid" | "error" | "in_progress", number>;
  };
  latency: { request: Latency; steps: StepLatency[] };
  indexing_latency: { request: Latency; steps: StepLatency[] };
  per_question: {
    questions_with_llm_call: number;
    mean_input_tokens: number | null;
    mean_output_tokens: number | null;
    mean_cost_usd: number | null;
    p95_cost_usd: number | null;
    total_input_tokens: number;
    total_output_tokens: number;
    total_cost_usd: number;
  };
  per_document: {
    uploads: number;
    index_rebuilds: number;
    graph_documents_read: number;
    graph_llm_calls: number;
    graph_failed_calls: number;
    graph_input_tokens: number;
    graph_output_tokens: number;
    graph_cost_usd: number;
    graph_cost_per_document_usd: number | null;
    graph_tokens_per_document: number | null;
  };
  per_day: {
    date: string;
    questions: number;
    answered: number;
    abstained: number;
    invalid: number;
    error: number;
    input_tokens: number;
    output_tokens: number;
    question_cost_usd: number;
    indexing_cost_usd: number;
    total_cost_usd: number;
  }[];
};

/** Plain names for trace steps; the technical name stays in the tooltip. */
const STEP_LABELS: Record<string, string> = {
  index_rebuild: "Updating the search index",
  retrieval: "Searching your documents",
  pii_redaction: "Removing personal data",
  llm_generation: "Writing the answer (LLM)",
  response_validation: "Checking the answer's format",
  citation_verification: "Checking the sources",
  load_documents: "Reading documents",
  chunking: "Splitting into passages",
  embedding_indexing: "Indexing for search",
  document_validation: "Checking the file",
  injection_scanning: "Scanning for injected instructions",
  document_storage: "Saving the document",
  graph_plan: "Planning the concept map",
  graph_extraction: "Extracting concepts (LLM)",
  graph_save: "Saving the concept map",
  concept_neighbourhood: "Opening a concept",
};

const OUTCOMES = [
  { key: "answered", label: "Answered", hint: "with checked sources" },
  { key: "abstained", label: "Not in the documents", hint: "BakeFix said so instead of guessing" },
  { key: "invalid", label: "Rejected answer", hint: "the LLM's answer failed the checks" },
  { key: "error", label: "Error", hint: "LLM unavailable, timeout, search error, bad request" },
  { key: "in_progress", label: "In progress", hint: "still running" },
] as const;

function ms(value: number | null): string {
  if (value === null) return "–";
  if (value < 1) return "<1 ms";
  return value < 1000 ? `${Math.round(value)} ms` : `${(value / 1000).toFixed(1)} s`;
}

function usd(value: number | null): string {
  if (value === null) return "–";
  if (value === 0) return "$0";
  return value < 0.01 ? `$${value.toFixed(5)}` : `$${value.toFixed(3)}`;
}

function count(value: number | null): string {
  return value === null ? "–" : Math.round(value).toLocaleString();
}

function percent(part: number, whole: number): string {
  return whole ? `${Math.round((part / whole) * 100)}%` : "–";
}

function isMetrics(value: unknown): value is Metrics {
  return typeof value === "object" && value !== null && "questions" in value && "per_day" in value;
}

export function MetricsPage() {
  const [days, setDays] = useState(7);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`/api/metrics?days=${days}`);
      const data = await readJson(response);
      if (!response.ok || !isMetrics(data)) {
        throw new Error(getApiErrorMessage(data, "The usage figures couldn’t be loaded."));
      }
      setMetrics(data);
      setError("");
    } catch (loadError) {
      setError(describeRequestError(loadError, "The usage figures couldn’t be loaded."));
    } finally {
      setIsLoading(false);
    }
  }, [days]);

  useEffect(() => {
    void load();
  }, [load]);

  const outcomes = metrics?.questions.outcomes;
  const finished = outcomes ? metrics.questions.total - outcomes.in_progress : 0;
  const totalCost = metrics ? metrics.per_question.total_cost_usd + metrics.per_document.graph_cost_usd : 0;
  const maxDayCost = metrics ? Math.max(0, ...metrics.per_day.map((d) => d.total_cost_usd)) : 0;

  return (
    <div className="metrics-page">
      <div className="metrics-toolbar">
        <label>
          Period
          <select id="metrics-days" value={days} onChange={(event) => setDays(Number(event.target.value))}>
            <option value={1}>Last 24 hours</option>
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days (all kept traces)</option>
          </select>
        </label>
        <button type="button" className="button secondary" onClick={() => void load()} disabled={isLoading}>
          {isLoading ? "Refreshing…" : "Refresh"}
        </button>
        {metrics && (
          <span className="metrics-source">
            Computed from {metrics.trace_count.toLocaleString()} traces stored on this computer.
          </span>
        )}
      </div>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {metrics && outcomes && (
        <>
          <section className="metrics-tiles" aria-label="Summary">
            <div className="metrics-tile">
              <span>Questions</span>
              <strong>{metrics.questions.total.toLocaleString()}</strong>
            </div>
            <div className="metrics-tile">
              <span>Answered with sources</span>
              <strong>{percent(outcomes.answered, finished)}</strong>
              <small>{outcomes.answered} of {finished}</small>
            </div>
            <div className="metrics-tile">
              <span>Time to answer</span>
              <strong>{ms(metrics.latency.request.p50_ms)}</strong>
              <small>typical · 95% within {ms(metrics.latency.request.p95_ms)}</small>
            </div>
            <div className="metrics-tile">
              <span>LLM cost</span>
              <strong>{usd(totalCost)}</strong>
              <small>questions and concept maps</small>
            </div>
          </section>

          {metrics.questions.total === 0 ? (
            <p className="metrics-empty">
              No questions in this period yet. Ask one and it will appear here, with its time and cost.
            </p>
          ) : (
            <section className="card metrics-card" aria-labelledby="metrics-outcomes">
              <h2 id="metrics-outcomes">What happened to each question</h2>
              <div className="outcome-bar" role="img" aria-label={OUTCOMES.map((o) => `${o.label}: ${outcomes[o.key]}`).join(", ")}>
                {OUTCOMES.filter((o) => outcomes[o.key] > 0).map((o) => (
                  <span
                    key={o.key}
                    className={`outcome-segment ${o.key}`}
                    style={{ flexGrow: outcomes[o.key] }}
                    title={`${o.label}: ${outcomes[o.key]}`}
                  />
                ))}
              </div>
              <ul className="outcome-legend">
                {OUTCOMES.map((o) => (
                  <li key={o.key}>
                    <span className={`outcome-swatch ${o.key}`} aria-hidden="true" />
                    <span className="outcome-name">{o.label}</span>
                    <span className="num">{outcomes[o.key]}</span>
                    <span className="num muted">{percent(outcomes[o.key], metrics.questions.total)}</span>
                    <small>{o.hint}</small>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className="card metrics-card" aria-labelledby="metrics-latency">
            <h2 id="metrics-latency">How long each step takes</h2>
            <p className="metrics-note">
              p50 is the typical time (half of the runs are faster); p95 is the slow case (95% of the runs are faster).
            </p>
            <LatencyTable latency={metrics.latency} firstRow="Whole question" />
          </section>

          <section className="metrics-pair">
            <section className="card metrics-card" aria-labelledby="metrics-question-cost">
              <h2 id="metrics-question-cost">Tokens and cost per question</h2>
              {metrics.per_question.questions_with_llm_call === 0 ? (
                <p className="metrics-empty">No question reached the LLM in this period.</p>
              ) : (
                <dl className="metrics-facts">
                  <div><dt>Questions sent to the LLM</dt><dd className="num">{metrics.per_question.questions_with_llm_call}</dd></div>
                  <div><dt>Average input tokens</dt><dd className="num">{count(metrics.per_question.mean_input_tokens)}</dd></div>
                  <div><dt>Average output tokens</dt><dd className="num">{count(metrics.per_question.mean_output_tokens)}</dd></div>
                  <div><dt>Average cost</dt><dd className="num">{usd(metrics.per_question.mean_cost_usd)}</dd></div>
                  <div><dt>Most expensive 5%</dt><dd className="num">from {usd(metrics.per_question.p95_cost_usd)}</dd></div>
                  <div><dt>Total</dt><dd className="num">{usd(metrics.per_question.total_cost_usd)}</dd></div>
                </dl>
              )}
            </section>

            <section className="card metrics-card" aria-labelledby="metrics-document-cost">
              <h2 id="metrics-document-cost">Cost per indexed document</h2>
              <dl className="metrics-facts">
                <div><dt>Documents added</dt><dd className="num">{metrics.per_document.uploads}</dd></div>
                <div><dt>Search indexing cost</dt><dd className="num">$0 <small>runs on this computer</small></dd></div>
                <div><dt>Documents read for the concept map</dt><dd className="num">{metrics.per_document.graph_documents_read}</dd></div>
                <div>
                  <dt>LLM calls for the concept map</dt>
                  <dd className="num">
                    {metrics.per_document.graph_llm_calls}
                    {metrics.per_document.graph_failed_calls > 0 && (
                      <small> ({metrics.per_document.graph_failed_calls} failed, retried next update)</small>
                    )}
                  </dd>
                </div>
                <div><dt>Tokens per document</dt><dd className="num">{count(metrics.per_document.graph_tokens_per_document)}</dd></div>
                <div><dt>Cost per document</dt><dd className="num">{usd(metrics.per_document.graph_cost_per_document_usd)}</dd></div>
              </dl>
            </section>
          </section>

          <section className="card metrics-card" aria-labelledby="metrics-days-title">
            <h2 id="metrics-days-title">Per day</h2>
            {metrics.per_day.length === 0 ? (
              <p className="metrics-empty">Nothing recorded in this period.</p>
            ) : (
              <div className="metrics-scroll">
                <table className="metrics-table">
                  <thead>
                    <tr>
                      <th>Day (UTC)</th>
                      <th>Questions</th>
                      <th>Answered</th>
                      <th>Not found</th>
                      <th>Rejected / error</th>
                      <th>Tokens in / out</th>
                      <th>Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {metrics.per_day.map((day) => (
                      <tr key={day.date}>
                        <td>{day.date}</td>
                        <td className="num">{day.questions}</td>
                        <td className="num">{day.answered}</td>
                        <td className="num">{day.abstained}</td>
                        <td className="num">{day.invalid} / {day.error}</td>
                        <td className="num">{day.input_tokens.toLocaleString()} / {day.output_tokens.toLocaleString()}</td>
                        <td className="num cost-cell">
                          <span
                            className="cost-bar"
                            style={{ width: maxDayCost ? `${(day.total_cost_usd / maxDayCost) * 100}%` : 0 }}
                            aria-hidden="true"
                          />
                          <span title={`Questions ${usd(day.question_cost_usd)} · concept map ${usd(day.indexing_cost_usd)}`}>
                            {usd(day.total_cost_usd)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <details className="card metrics-card metrics-details">
            <summary>Indexing runs: time per step</summary>
            <LatencyTable latency={metrics.indexing_latency} firstRow="Whole indexing run" />
          </details>

          <details className="card metrics-card metrics-details">
            <summary>How these numbers are computed</summary>
            <ul className="metrics-definitions">
              <li>Every number comes from the traces BakeFix records for each question and each indexing run; nothing is counted separately.</li>
              <li><strong>Answered / not found</strong> come from the trace's outcome. A failed question is a <strong>rejected answer</strong> when the LLM's answer failed the format or source checks, and an <strong>error</strong> otherwise.</li>
              <li><strong>Time</strong> is measured from when the question arrived to when the answer was sent; each step is its own timed span. p50 and p95 use the nearest-rank method.</li>
              <li><strong>Tokens and cost</strong> come from the LLM step of each trace. Search indexing runs on this computer and costs nothing; only the concept map calls the LLM when indexing.</li>
              <li>Traces are kept for 30 days, so that is the longest period shown.</li>
            </ul>
          </details>
        </>
      )}
    </div>
  );
}

function LatencyTable({ latency, firstRow }: { latency: { request: Latency; steps: StepLatency[] }; firstRow: string }) {
  if (latency.request.count === 0 && latency.steps.length === 0) {
    return <p className="metrics-empty">Nothing recorded in this period.</p>;
  }
  return (
    <div className="metrics-scroll">
      <table className="metrics-table compact">
        <thead>
          <tr>
            <th>Step</th>
            <th>Runs</th>
            <th>p50</th>
            <th>p95</th>
          </tr>
        </thead>
        <tbody>
          <tr className="metrics-total">
            <td>{firstRow}</td>
            <td className="num">{latency.request.count}</td>
            <td className="num">{ms(latency.request.p50_ms)}</td>
            <td className="num">{ms(latency.request.p95_ms)}</td>
          </tr>
          {latency.steps.map((step) => (
            <tr key={step.step}>
              <td title={step.step}>{STEP_LABELS[step.step] ?? step.step}</td>
              <td className="num">{step.count}</td>
              <td className="num">{ms(step.p50_ms)}</td>
              <td className="num">{ms(step.p95_ms)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
