import type {
  Answer,
  AnswerReference,
  GlossaryEntry,
  AskRetrieval,
  GraphEntity,
  GraphPath,
} from "../types/api";
import ReactMarkdown from "react-markdown";
import { describeStyle } from "./AnswerStyleControls";
import { TraceDetails } from "./TraceDetails";
import "../../styles/retriever-controls.css";

type AnswerPanelProps = {
  answer: Answer;
  onRetry: () => void;
};

/** Make the start of a passage readable as a quote: drop Markdown markers. */
function cleanQuote(text: string): string {
  const plain = text
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/\*\*|__|`/g, "")
    .replace(/\s+/g, " ")
    .trim();
  if (plain.length < 240) {
    return plain;
  }
  const cut = plain.slice(0, 240);
  return `${cut.slice(0, cut.lastIndexOf(" ") > 0 ? cut.lastIndexOf(" ") : 240)}…`;
}

export function AnswerPanel({ answer, onRetry }: AnswerPanelProps) {
  if (answer.kind === "loading") {
    return (
      <div className="answer-placeholder">
        <span className="placeholder-mark" aria-hidden="true">
          ~
        </span>
        <p>Reading your documents and writing an answer… This usually takes a few seconds.</p>
      </div>
    );
  }

  if (answer.kind === "error") {
    return (
      <div className="answer-error" role="alert">
        <div className="answer-title">Something went wrong</div>
        <p>{answer.text}</p>
        {answer.retryable !== false && (
          <button type="button" className="button secondary" onClick={onRetry}>
            Try again
          </button>
        )}
        <TraceDetails key={answer.trace_id ?? "none"} traceId={answer.trace_id} />
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
        {answer.kind === "not_found" ? "Not in your documents" : "Answer"}
      </div>
      {answer.kind === "answered" && (
        <p className="answer-style-used">
          Written {describeStyle(answer.style)}
        </p>
      )}
      {answer.kind === "not_found" ? (
        <div className="answer-copy not-found">
          <p>{answer.text}</p>
          <p className="not-found-help">What you can try:</p>
          <ul className="not-found-tips">
            <li>Rephrase the question with the words your documents use.</li>
            <li>
              Check “Search options”: some of your documents may be left out.
            </li>
            <li>Add a recipe, note or manual that covers this topic.</li>
          </ul>
        </div>
      ) : (
        <div className="answer-copy answer-markdown">
          <ReactMarkdown skipHtml>{answer.text}</ReactMarkdown>
        </div>
      )}
      {answer.kind === "answered" && answer.references.length > 0 && (
        <div className="references">
          <h3>Where this comes from</h3>
          <ul>
            {answer.references.map((reference, index) => (
              <li key={`${reference.chunk_id}-${reference.position}`}>
                <span className="reference-meta">
                  [{index + 1}] {reference.source} · passage{" "}
                  {reference.position + 1}
                </span>
                <span className="reference-quote">
                  “{cleanQuote(reference.quote)}”
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {answer.kind === "answered" && answer.glossary.length > 0 && (
        <Glossary entries={answer.glossary} references={answer.references} />
      )}
      {answer.retrieval && <RetrievalDetails retrieval={answer.retrieval} />}
      <TraceDetails key={answer.trace_id ?? "none"} traceId={answer.trace_id} />
    </>
  );
}

/** Terms used in the answer, each defined from a passage the answer cites. */
function Glossary({
  entries,
  references,
}: {
  entries: GlossaryEntry[];
  references: AnswerReference[];
}) {
  const sourceNumber = new Map(
    references.map((reference, index) => [reference.chunk_id, index + 1]),
  );

  return (
    <section className="glossary" aria-labelledby="glossary-title">
      <h3 id="glossary-title">Words to know</h3>
      <dl>
        {entries.map((entry) => {
          const number = sourceNumber.get(entry.chunk_id);
          return (
            <div key={`${entry.term}-${entry.chunk_id}`}>
              <dt>{entry.term}</dt>
              <dd>
                {entry.definition}
                {number !== undefined && (
                  <span
                    className="glossary-source"
                    title={`Defined from source [${number}]`}
                  >
                    {" "}
                    [{number}]
                  </span>
                )}
              </dd>
            </div>
          );
        })}
      </dl>
    </section>
  );
}

function RetrievalDetails({ retrieval }: { retrieval: AskRetrieval }) {
  const graphChunksById = new Map(
    retrieval.graph_supporting_chunks.map((chunk) => [chunk.id, chunk]),
  );

  return (
    <details className="retrieval-details">
      <summary>How BakeFix found these passages (technical details)</summary>
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
    </details>
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
