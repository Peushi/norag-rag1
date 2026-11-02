import { useState } from "react";
import "../../styles/words.css";
import { useRetrievalComparison } from "../hooks/useRetrievalComparison";
import type { EvaluationDataset } from "../types/evaluations";
import type {
  RetrievalConfigurationResult,
  RetrievalMetricValues,
  RetrievalQuestionResult,
} from "../types/retrievalComparisons";

type RetrievalComparisonProps = {
  dataset: EvaluationDataset;
};

function formatPercent(value: number | null | undefined): string {
  return value === null || value === undefined
    ? "—"
    : `${(value * 100).toFixed(1)}%`;
}

function MetricTable({
  metrics,
  kValues,
}: {
  metrics: Record<string, RetrievalMetricValues>;
  kValues: number[];
}) {
  return (
    <table className="retrieval-metric-table">
      <thead>
        <tr>
          <th scope="col">k</th>
          <th scope="col">HitRate</th>
          <th scope="col">Evidence Recall</th>
        </tr>
      </thead>
      <tbody>
        {kValues.map((k) => (
          <tr key={k}>
            <th scope="row">{k}</th>
            <td>{formatPercent(metrics[String(k)]?.hit_rate)}</td>
            <td>{formatPercent(metrics[String(k)]?.recall)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function QuestionDetails({
  question,
  kValues,
}: {
  question: RetrievalQuestionResult;
  kValues: number[];
}) {
  return (
    <details className="retrieval-question">
      <summary>
        <span>
          <strong>{question.id}</strong> · {question.question}
        </span>
        <span className="retrieval-question-summary">
          {question.answerable ? question.type : "unanswerable"}
        </span>
      </summary>
      {!question.answerable ? (
        <p className="retrieval-unanswerable">
          Unanswerable in this corpus; excluded from aggregate HitRate and
          Recall.
        </p>
      ) : (
        <>
          <h5>Per-question metrics</h5>
          <div className="retrieval-question-metrics">
            {kValues.map((k) => {
              const metric = question.retrieval_metrics?.[String(k)];
              return (
                <span key={k}>
                  @{k}: {metric?.hit ? "hit" : "miss"} · Recall{" "}
                  {formatPercent(metric?.recall)}
                </span>
              );
            })}
          </div>
          <h5>Expected evidence</h5>
          {question.evidence.length > 0 ? (
            <ul className="retrieval-evidence-list">
              {question.evidence.map((evidence, index) => (
                <li key={`${evidence.source}-${index}`}>
                  <strong>{evidence.source}</strong>
                  <blockquote>{evidence.quote}</blockquote>
                  <span>
                    {evidence.matched_chunks.length
                      ? `Found at rank${evidence.matched_chunks.length === 1 ? "" : "s"} ${evidence.matched_chunks.map((chunk) => chunk.rank).join(", ")}`
                      : "Not recovered in the top 10"}
                    {evidence.boundary_split && " · quote crosses a chunk boundary"}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p>No expected evidence was labeled for this question.</p>
          )}
        </>
      )}
      <h5>Retrieved passages (evaluation top 10)</h5>
      {question.evaluation_chunks.length ? (
        <ol className="retrieval-passages">
          {question.evaluation_chunks.map((passage) => (
            <li key={passage.id}>
              <div className="retrieval-passage-heading">
                <strong>Rank {passage.rank}</strong>
                <span>{passage.source}</span>
                <span>Chunk {passage.position + 1}</span>
                <span>Distance {passage.distance.toFixed(4)}</span>
                <span
                  className={
                    passage.relevant
                      ? "retrieval-relevance relevant"
                      : "retrieval-relevance"
                  }
                >
                  {passage.relevant ? "Labeled relevant" : "No labeled quote"}
                </span>
              </div>
              <p>{passage.text}</p>
              {passage.matched_evidence_quotes.length > 0 && (
                <ul>
                  {passage.matched_evidence_quotes.map((quote) => (
                    <li key={quote}>{quote}</li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ol>
      ) : (
        <p>No passages were retrieved.</p>
      )}
    </details>
  );
}

function ConfigurationSection({
  configuration,
  selectedK,
}: {
  configuration: RetrievalConfigurationResult;
  selectedK: number;
}) {
  return (
    <section
      className="retrieval-configuration"
      aria-labelledby={`retrieval-config-${configuration.config_id}`}
    >
      <div className="retrieval-config-heading">
        <div>
          <h3 id={`retrieval-config-${configuration.config_id}`}>
            {configuration.chunk_size}/{configuration.overlap}
          </h3>
          <p>
            {configuration.answerable_questions} answerable ·{" "}
            {configuration.excluded_questions} excluded ·{" "}
            {configuration.generate_answers
              ? "answer generation enabled"
              : "retrieval only"}
          </p>
        </div>
        <span>{configuration.config_id}</span>
      </div>

      <h4>Aggregate metrics</h4>
      <MetricTable
        metrics={configuration.metrics}
        kValues={configuration.top_k_values}
      />

      <h4>Question-type breakdown at k = {selectedK}</h4>
      <div className="retrieval-breakdown-wrap">
        <table className="retrieval-breakdown-table">
          <thead>
            <tr>
              <th scope="col">Question type</th>
              <th scope="col">Answerable</th>
              <th scope="col">Excluded</th>
              <th scope="col">HitRate@{selectedK}</th>
              <th scope="col">Recall@{selectedK}</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(configuration.question_type_breakdown).map(
              ([questionType, summary]) => {
                const metrics = summary.metrics[String(selectedK)];
                return (
                  <tr key={questionType}>
                    <th scope="row">{questionType}</th>
                    <td>{summary.answerable_questions}</td>
                    <td>{summary.excluded_questions}</td>
                    <td>{formatPercent(metrics?.hit_rate)}</td>
                    <td>{formatPercent(metrics?.recall)}</td>
                  </tr>
                );
              },
            )}
          </tbody>
        </table>
      </div>

      <details className="retrieval-questions">
        <summary>Per-question results ({configuration.questions.length})</summary>
        <div className="retrieval-questions-list">
          {configuration.questions.map((question) => (
            <QuestionDetails
              key={question.id}
              question={question}
              kValues={configuration.top_k_values}
            />
          ))}
        </div>
      </details>
    </section>
  );
}

export function RetrievalComparison({ dataset }: RetrievalComparisonProps) {
  const [selectedK, setSelectedK] = useState(5);
  const { comparison, isLoading, error } = useRetrievalComparison(dataset);

  return (
    <section
      className="card retrieval-comparison-card"
      aria-labelledby="retrieval-comparison-title"
    >
      <div className="section-heading">
        <span className="section-icon" aria-hidden="true">
          R
        </span>
        <div>
          <h2 id="retrieval-comparison-title">Retrieval comparison</h2>
          <p>
            Compare the measured 800/80 baseline with 400/40 using passage-level
            evidence matching.
          </p>
        </div>
      </div>

      {isLoading && <p role="status">Loading retrieval comparison...</p>}
      {error && (
        <p className="error evaluation-error" role="alert">
          {error}
        </p>
      )}
      {comparison && (
        <>
          <div className="retrieval-metadata">
            <span>
              <strong>Dataset:</strong> {comparison.dataset}
            </span>
            <span>
              <strong>Embedding:</strong> {comparison.embedding_model}
            </span>
            <span>
              <strong>Distance:</strong> {comparison.distance_metric}
            </span>
            <span>
              <strong>Experiment:</strong> {comparison.experiment_id}
            </span>
          </div>
          <p className="retrieval-method-note">
            Relevant evidence requires the expected source and complete quote
            in one chunk (whitespace normalized). Recall is averaged per
            answerable question; unanswerable questions are excluded.
          </p>
          <label className="retrieval-k-selector">
            Question-type breakdown k
            <select
              value={selectedK}
              onChange={(event) => setSelectedK(Number(event.target.value))}
            >
              {[1, 3, 5, 10].map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </label>
          <div className="retrieval-configurations">
            {comparison.configurations.map((configuration) => (
              <ConfigurationSection
                key={configuration.config_id}
                configuration={configuration}
                selectedK={selectedK}
              />
            ))}
          </div>
          <p className="retrieval-method-note">
            {comparison.relevance_rule}. {comparison.recall_averaging}.
          </p>
        </>
      )}
    </section>
  );
}
