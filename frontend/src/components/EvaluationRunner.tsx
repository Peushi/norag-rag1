import { useState, type FormEvent } from "react";
import { useEvaluationRunner } from "../hooks/useEvaluationRunner";
import type {
  EvaluationDataset,
  EvaluationRunRequest,
} from "../types/evaluations";

type EvaluationRunnerProps = {
  dataset: EvaluationDataset;
  onDatasetChange: (dataset: EvaluationDataset) => void;
};

export function EvaluationRunner({
  dataset,
  onDatasetChange,
}: EvaluationRunnerProps) {
  const [topK, setTopK] = useState("5");
  const [chunkSize, setChunkSize] = useState("800");
  const [overlap, setOverlap] = useState("80");
  const [maxDistance, setMaxDistance] = useState("");
  const [limit, setLimit] = useState("");
  const { run, results, isStarting, error, startEvaluation } =
    useEvaluationRunner();

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const request: EvaluationRunRequest = {
      dataset,
      top_k: Number(topK),
      chunk_size: Number(chunkSize),
      overlap: Number(overlap),
      max_distance: maxDistance === "" ? null : Number(maxDistance),
      limit: limit === "" ? null : Number(limit),
    };
    void startEvaluation(request);
  }

  const answerableResults =
    results?.results.filter((result) => result.answerable !== false) ?? [];
  const hitCount = answerableResults.filter(
    (result) => result.retrieval_hit === true,
  ).length;

  return (
    <section className="card evaluation-card" aria-labelledby="evaluation-title">
      <div className="section-heading">
        <span className="section-icon" aria-hidden="true">
          %
        </span>
        <div>
          <h2 id="evaluation-title">Run an evaluation</h2>
          <p>Compare a retrieval run on the selected question set.</p>
        </div>
      </div>

      <form className="evaluation-form" onSubmit={handleSubmit}>
        <label>
          Question set
          <select
            value={dataset}
            onChange={(event) =>
              onDatasetChange(
                event.target.value === "kestrel" ? "kestrel" : "baking",
              )
            }
          >
            <option value="baking">Baking</option>
            <option value="kestrel">Kestrel</option>
          </select>
        </label>
        <label>
          Top-k
          <input
            type="number"
            min="1"
            max="20"
            required
            value={topK}
            onChange={(event) => setTopK(event.target.value)}
          />
        </label>
        <label>
          Chunk size
          <input
            type="number"
            min="100"
            max="2000"
            required
            value={chunkSize}
            onChange={(event) => setChunkSize(event.target.value)}
          />
        </label>
        <label>
          Overlap
          <input
            type="number"
            min="0"
            max="1000"
            required
            value={overlap}
            onChange={(event) => setOverlap(event.target.value)}
          />
        </label>
        <label>
          Maximum distance <span className="optional-label">(optional)</span>
          <input
            type="number"
            min="0"
            max="2"
            step="0.01"
            value={maxDistance}
            onChange={(event) => setMaxDistance(event.target.value)}
          />
        </label>
        <label>
          Question limit <span className="optional-label">(optional)</span>
          <input
            type="number"
            min="1"
            max="1000"
            value={limit}
            onChange={(event) => setLimit(event.target.value)}
          />
        </label>
        <button
          className="button"
          type="submit"
          disabled={isStarting || run?.status === "queued" || run?.status === "running"}
        >
          {isStarting || run?.status === "queued" || run?.status === "running"
            ? "Evaluation running..."
            : `Evaluate ${dataset}`}
        </button>
      </form>

      {error && (
        <p className="error evaluation-error" role="alert">
          {error}
        </p>
      )}

      {run && (
        <div className="evaluation-run-status" role="status" aria-live="polite">
          <strong>Run {run.run_id.slice(0, 8)}:</strong> {run.status}
          {run.error && <p className="error">{run.error}</p>}
        </div>
      )}

      {results && (
        <section className="evaluation-results" aria-labelledby="results-title">
          <h3 id="results-title">Results</h3>
          <p>
            {results.results.length} questions · {hitCount}/
            {answerableResults.length} answerable questions had an expected
            source in the retrieved results.
          </p>
          <ul>
            {results.results.map((result) => (
              <li key={result.id}>
                <strong>{result.id}</strong> — {result.status ?? "unknown"}
                {result.retrieval_hit === true && " · retrieval hit"}
                {result.retrieval_hit === false && " · retrieval miss"}
                {typeof result.manual_review === "object" &&
                  result.manual_review !== null &&
                  result.manual_review.grade &&
                  ` · grade: ${result.manual_review.grade}`}
                {result.error && <span className="error"> · {result.error}</span>}
              </li>
            ))}
          </ul>
        </section>
      )}
    </section>
  );
}
