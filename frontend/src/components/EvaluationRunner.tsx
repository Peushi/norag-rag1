import { useState, type FormEvent } from "react";
import "../../styles/evaluation.css";
import { useEvaluationRunner } from "../hooks/useEvaluationRunner";
import type {
  EvaluationDataset,
  EvaluationResult,
  EvaluationRunRequest,
} from "../types/evaluations";
import type { RetrieverName } from "../types/api";

type RetrieverConfigurationId =
  | "dense"
  | "bm25"
  | "dense_bm25"
  | "graph"
  | "dense_graph"
  | "dense_bm25_graph";

const RETRIEVER_CONFIGURATIONS: Array<{
  id: RetrieverConfigurationId;
  label: string;
  retrievers: RetrieverName[];
  requiresKestrel?: boolean;
}> = [
  { id: "dense", label: "Dense", retrievers: ["dense"] },
  { id: "bm25", label: "BM25", retrievers: ["bm25"] },
  {
    id: "dense_bm25",
    label: "Dense + BM25 (RRF)",
    retrievers: ["dense", "bm25"],
  },
  { id: "graph", label: "Graph (Kestrel)", retrievers: ["graph"], requiresKestrel: true },
  {
    id: "dense_graph",
    label: "Dense + Graph (RRF, Kestrel)",
    retrievers: ["dense", "graph"],
    requiresKestrel: true,
  },
  {
    id: "dense_bm25_graph",
    label: "Dense + BM25 + Graph (RRF, Kestrel)",
    retrievers: ["dense", "bm25", "graph"],
    requiresKestrel: true,
  },
];

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
  const [chunkingPreset, setChunkingPreset] = useState("800/80");
  const [maxDistance, setMaxDistance] = useState("");
  const [limit, setLimit] = useState("");
  const [configurationId, setConfigurationId] =
    useState<RetrieverConfigurationId>("dense");
  const [generateAnswers, setGenerateAnswers] = useState(false);
  const [comparePathContext, setComparePathContext] = useState(false);
  const { run, results, isStarting, error, startEvaluation } =
    useEvaluationRunner();
  const configuration = RETRIEVER_CONFIGURATIONS.find(
    (item) => item.id === configurationId,
  )!;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const request: EvaluationRunRequest = {
      dataset,
      top_k: Number(topK),
      chunk_size: Number(chunkSize),
      overlap: Number(overlap),
      max_distance: maxDistance === "" ? null : Number(maxDistance),
      limit: limit === "" ? null : Number(limit),
      retrievers: configuration.retrievers,
      compare_path_context: comparePathContext,
      generate_answers: generateAnswers || comparePathContext,
    };
    void startEvaluation(request);
  }

  function updateDataset(nextDataset: EvaluationDataset) {
    onDatasetChange(nextDataset);
    if (
      nextDataset !== "kestrel" &&
      configuration.requiresKestrel
    ) {
      setConfigurationId("dense");
      setComparePathContext(false);
    }
  }

  function updateChunkingPreset(value: string) {
    setChunkingPreset(value);
    if (value === "800/80") {
      setChunkSize("800");
      setOverlap("80");
    } else if (value === "400/40") {
      setChunkSize("400");
      setOverlap("40");
    }
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
              updateDataset(
                event.target.value === "kestrel" ? "kestrel" : "baking",
              )
            }
          >
            <option value="baking">Baking</option>
            <option value="kestrel">Kestrel</option>
          </select>
        </label>
        <label>
          Retriever configuration
          <select
            value={configurationId}
            onChange={(event) => {
              const nextConfiguration = RETRIEVER_CONFIGURATIONS.find(
                (option) => option.id === event.target.value,
              );
              if (nextConfiguration) {
                setConfigurationId(nextConfiguration.id);
                setComparePathContext(false);
              }
            }}
          >
            {RETRIEVER_CONFIGURATIONS.map((option) => (
              <option
                disabled={option.requiresKestrel && dataset !== "kestrel"}
                key={option.id}
                value={option.id}
              >
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <p className="evaluation-config-note">
          Multiple retrievers are fused with RRF. Current evaluation adapters
          support Dense only; unregistered methods fail explicitly rather than
          falling back.
        </p>
        <label>
          Chunking preset
          <select
            value={chunkingPreset}
            onChange={(event) => updateChunkingPreset(event.target.value)}
          >
            <option value="800/80">Baseline (800/80)</option>
            <option value="400/40">Smaller chunks (400/40)</option>
            <option value="custom">Custom</option>
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
            onChange={(event) => {
              setChunkSize(event.target.value);
              setChunkingPreset("custom");
            }}
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
            onChange={(event) => {
              setOverlap(event.target.value);
              setChunkingPreset("custom");
            }}
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
        <label className="evaluation-checkbox">
          <input
            type="checkbox"
            checked={generateAnswers || comparePathContext}
            onChange={(event) => setGenerateAnswers(event.target.checked)}
            disabled={comparePathContext}
          />
          Generate answers for manual review
        </label>
        {configuration.retrievers.includes("graph") && (
          <label className="evaluation-checkbox">
            <input
              type="checkbox"
              checked={comparePathContext}
              onChange={(event) => {
                setComparePathContext(event.target.checked);
                if (event.target.checked) {
                  setGenerateAnswers(true);
                }
              }}
            />
            Compare Path as Context off/on
          </label>
        )}
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
            <strong>Configuration:</strong> {configurationLabel(run?.retrievers ?? ["dense"])} ·{" "}
            {run?.chunk_size}/{run?.overlap}
            {run?.compare_path_context ? " · Path as Context comparison" : ""}
          </p>
          <EvaluationMetricSummary results={results.results} />
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

function configurationLabel(retrievers: RetrieverName[]): string {
  return (
    RETRIEVER_CONFIGURATIONS.find(
      (configuration) =>
        configuration.retrievers.length === retrievers.length &&
        configuration.retrievers.every((retriever) =>
          retrievers.includes(retriever),
        ),
    )?.label ?? retrievers.join(" + ")
  );
}

function EvaluationMetricSummary({
  results,
}: {
  results: EvaluationResult[];
}) {
  const answerable = results.filter(
    (result) => result.answerable && result.retrieval_metrics,
  );
  const types = [...new Set(answerable.map((result) => result.type ?? "other"))].sort();
  const rows = [
    { label: "Overall", results: answerable },
    ...types.map((type) => ({
      label: type,
      results: answerable.filter((result) => (result.type ?? "other") === type),
    })),
  ];

  if (answerable.length === 0) {
    return <p>Evidence metrics are not available for this run.</p>;
  }

  return (
    <div className="evaluation-metrics-wrap">
      <table className="evaluation-metrics">
        <caption>Hit rate and macro evidence recall by question type</caption>
        <thead>
          <tr>
            <th scope="col">Question group</th>
            <th scope="col">Answerable</th>
            {[1, 3, 5, 10].flatMap((k) => [
              <th key={`hit-${k}`} scope="col">Hit@{k}</th>,
              <th key={`recall-${k}`} scope="col">Recall@{k}</th>,
            ])}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <th scope="row">{row.label}</th>
              <td>{row.results.length}</td>
              {[1, 3, 5, 10].flatMap((k) => {
                const metrics = row.results
                  .map((result) => result.retrieval_metrics?.[String(k)])
                  .filter((metric) => metric !== undefined && metric !== null);
                const hitRate =
                  metrics.length === 0
                    ? null
                    : metrics.filter((metric) => metric.hit).length /
                      metrics.length;
                const recall =
                  metrics.length === 0
                    ? null
                    : metrics.reduce((sum, metric) => sum + metric.recall, 0) /
                      metrics.length;
                return [
                  <td key={`hit-${k}`}>
                    {hitRate === null ? "—" : `${(hitRate * 100).toFixed(1)}%`}
                  </td>,
                  <td key={`recall-${k}`}>
                    {recall === null ? "—" : `${(recall * 100).toFixed(1)}%`}
                  </td>,
                ];
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
