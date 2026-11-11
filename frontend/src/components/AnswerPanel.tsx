import { useState } from "react";
import type {
  Answer,
  AskRetrieval,
  GraphEntity,
  GraphPath,
  TraceDetail,
} from "../types/api";
import ReactMarkdown from "react-markdown";
import { getApiErrorMessage, isTraceDetail } from "../types/api";
import "../../styles/retriever-controls.css";

type AnswerPanelProps = {
  answer: Answer;
};

export function AnswerPanel({ answer }: AnswerPanelProps) {
  if (answer.kind === "loading") {
    return (
      <div className="answer-placeholder">
        <span className="placeholder-mark" aria-hidden="true">
          ~
        </span>
        <p>Gathering the helpful bits...</p>
      </div>
    );
  }

  if (answer.kind === "error") {
    return (
      <div className="error">
        <p>{answer.text}</p>
        <TraceDetails traceId={answer.trace_id} />
      </div>
    );
  }

  if (answer.kind === "empty") {
    return (
      <div className="answer-placeholder">
        <span className="placeholder-mark" aria-hidden="true">
          ~
        </span>
        <p>{answer.text}</p>
      </div>
    );
  }

  return (
    <>
      <div className="answer-title">
        {answer.kind === "not_found" ? "Not in your notes yet" : "A little guidance"}
      </div>
      <p
        className={`answer-copy${answer.kind === "not_found" ? " not-found" : ""}`}
      >
        {answer.text}
      </p>
      {answer.kind === "answered" && answer.references.length > 0 && (
        <div className="references">
          <h3>From your notes</h3>
          <ul>
            {answer.references.map((reference) => (
              <li key={`${reference.chunk_id}-${reference.position}`}>
                <span className="reference-meta">
                  {reference.source} · note {reference.position + 1}
                </span>
                <span className="reference-quote">“{reference.quote}”</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {answer.retrieval && <RetrievalDetails retrieval={answer.retrieval} />}
      <TraceDetails traceId={answer.trace_id} />
    </>
  );
}

function TraceDetails({ traceId }: { traceId?: string | null }) {
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
    if (trace) {
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
          {error && <p className="error" role="alert">{error}</p>}
          {trace && (
            <>
              <p>
                Trace {trace.trace_id} · {trace.status}
                {trace.outcome ? ` · ${trace.outcome}` : ""}
              </p>
              <ol className="trace-span-list">
                {trace.spans.map((span, index) => (
                  <li key={`${span.name}-${index}`}>
                    <strong>{span.name}</strong>
                    <span>{span.status} · {span.duration_ms.toFixed(1)} ms</span>
                    {Object.keys(span.attributes).length > 0 && (
                      <dl>
                        {Object.entries(span.attributes).map(([key, value]) => (
                          <div key={key}>
                            <dt>{key}</dt>
                            <dd>{String(value)}</dd>
                          </div>
                        ))}
                      </dl>
                    )}
                    {span.error_type && (
                      <span className="error">Failed: {span.error_type}</span>
                    )}
                  </li>
                ))}
              </ol>
            </>
          )}
        </div>
      )}
    </section>
  );
}

function RetrievalDetails({ retrieval }: { retrieval: AskRetrieval }) {
  const graphChunksById = new Map(
    retrieval.graph_supporting_chunks.map((chunk) => [chunk.id, chunk]),
  );

  return (
    <section className="retrieval-details" aria-label="Retrieval details">
      <h3>How the evidence was found</h3>
      <ul className="retrieval-method-list">
        {retrieval.retrievers.map((retriever) => (
          <li key={retriever}>{retrieverLabel(retriever)}</li>
        ))}
      </ul>
      {retrieval.chunks.length > 0 && (
        <ol className="fused-chunk-list" aria-label="Fused retrieved chunks">
          {retrieval.chunks.map((chunk) => (
            <li className="fused-chunk" key={chunk.id}>
              <div className="fused-chunk-heading">
                <span>Fused rank {chunk.final_rank}</span>
                <span>RRF score {chunk.final_score.toFixed(4)}</span>
              </div>
              <p className="fused-chunk-meta">
                {chunk.source} · chunk {chunk.position + 1} · {chunk.id}
              </p>
              <p className="fused-contributions">
                Found by{" "}
                {chunk.retrievers
                  .map((contribution) => {
                    const score =
                      typeof contribution.score === "number" &&
                      contribution.score_type
                        ? `, ${contribution.score_type}: ${contribution.score.toFixed(4)}`
                        : "";
                    return `${retrieverLabel(contribution.retriever)} rank ${contribution.rank}${score}`;
                  })
                  .join("; ")}
              </p>
              <div className="fused-chunk-text">
                <ReactMarkdown skipHtml>{chunk.text}</ReactMarkdown>
              </div>
            </li>
          ))}
        </ol>
      )}
      {retrieval.graph_paths.length > 0 && (
        <div className="graph-paths">
          <h3>Concept graph paths</h3>
          <ol className="graph-path-list">
            {retrieval.graph_paths.map((path, index) => (
              <GraphPathDetails
                graphPath={path}
                index={index}
                graphChunksById={graphChunksById}
                key={`${path.supporting_chunk_ids.join("-")}-${index}`}
              />
            ))}
          </ol>
          {retrieval.path_context && (
            <p className="fused-chunk-meta">
              These graph paths and supporting passages were included in the
              answer-generation context.
            </p>
          )}
        </div>
      )}
    </section>
  );
}

function GraphPathDetails({
  graphPath,
  index,
  graphChunksById,
}: {
  graphPath: GraphPath;
  index: number;
  graphChunksById: Map<string, AskRetrieval["graph_supporting_chunks"][number]>;
}) {
  const entities = graphPath.entities.map(entityLabel);
  const supportingIds = new Set(graphPath.supporting_chunk_ids);
  const supportingChunks = [...supportingIds]
    .map((id) => graphChunksById.get(id))
    .filter((chunk) => chunk !== undefined);

  return (
    <li className="graph-path">
      <h4>Path {index + 1}</h4>
      <p className="graph-path-chain">{entities.join(" → ") || "Path details unavailable"}</p>
      {graphPath.edges.length > 0 && (
        <ol className="graph-path-edges">
          {graphPath.edges.map((edge, edgeIndex) => (
            <li key={`${edge.relation ?? edge.relation_type ?? "relation"}-${edgeIndex}`}>
              {[
                edgeEntityLabel(edge.source_entity ?? edge.source),
                edge.relation ?? edge.relation_type ?? edge.type,
                edgeEntityLabel(edge.target_entity ?? edge.target),
              ]
                .filter((part): part is string => Boolean(part))
                .join(" — ") || "Relationship"}
              {edge.evidence_quote && (
                <span className="graph-evidence-quote">
                  “{edge.evidence_quote}”
                </span>
              )}
              {edge.evidence_quotes?.map((quote, quoteIndex) => (
                <span
                  className="graph-evidence-quote"
                  key={`${edgeIndex}-quote-${quoteIndex}`}
                >
                  “{quote}”
                </span>
              ))}
            </li>
          ))}
        </ol>
      )}
      {supportingChunks.length > 0 ? (
        <details className="graph-supporting-chunks">
          <summary>
            Source passages ({supportingChunks.length})
          </summary>
          {supportingChunks.map((chunk) => (
            <div className="graph-supporting-chunk" key={chunk.id}>
              <span className="reference-meta">
                {chunk.source} · chunk {chunk.position + 1} · {chunk.id}
              </span>
              <div className="fused-chunk-text">
                <ReactMarkdown skipHtml>{chunk.text}</ReactMarkdown>
              </div>
            </div>
          ))}
        </details>
      ) : (
        <p className="fused-chunk-meta">
          Supporting chunk IDs: {[...supportingIds].join(", ") || "not provided"}
        </p>
      )}
    </li>
  );
}

function entityLabel(entity: GraphEntity): string {
  if (typeof entity === "string") {
    return entity;
  }
  return entity.name ?? entity.id ?? "Unknown entity";
}

function edgeEntityLabel(entity: GraphEntity | undefined): string | undefined {
  return entity ? entityLabel(entity) : undefined;
}

function retrieverLabel(retriever: string): string {
  if (retriever === "dense") {
    return "Dense";
  }
  if (retriever === "bm25") {
    return "BM25";
  }
  return "Graph";
}
