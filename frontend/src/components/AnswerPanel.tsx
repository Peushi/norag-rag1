import type {
  Answer,
  AnswerReference,
  GlossaryEntry,
  AskRetrieval,
  GraphEntity,
  GraphPath,
} from "../types/api";
import { useState, type CSSProperties } from "react";
import { SafeMarkdown } from "./SafeMarkdown";
import { AnswerActions } from "./AnswerActions";
import { BakingLoader } from "./BakingLoader";
import { describeStyle } from "./AnswerStyleControls";
import { TraceDetails } from "./TraceDetails";
import { documentCategory, documentTitle } from "../utils/documentNames";
import "../../styles/retriever-controls.css";

type AnswerPanelProps = {
  answer: Answer;
  onRetry: () => void;
};

// Front-matter lines at the top of bundled documents ("Source: https://…").
const METADATA_LINE = /^\s*(source|source title|publisher|published|author|topic|updated|url)\s*:.*$/gim;

/**
 * Make a passage readable as a quote: drop Markdown markers and metadata
 * lines, and start and end on whole words. Passages are cut by character
 * count, so one that is not the first can start in the middle of a word.
 */
export function cleanQuote(text: string, position = 0): string {
  let plain = text
    .replace(METADATA_LINE, "")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/\*\*|__|`/g, "")
    .replace(/https?:\/\/\S+/g, "")
    .replace(/\s+/g, " ")
    .trim();
  let leading = "";
  if (position > 0 && /^[a-z]/.test(plain)) {
    const firstSpace = plain.indexOf(" ");
    plain = firstSpace > 0 ? plain.slice(firstSpace + 1) : plain;
    leading = "…";
  }
  if (plain.length < 240) {
    // Stored quotes are cut by length too: end on a whole word.
    const lastSpace = plain.lastIndexOf(" ");
    const endsCleanly = /[.!?:;)"”’]$/.test(plain);
    return endsCleanly || lastSpace < 0
      ? leading + plain
      : `${leading}${plain.slice(0, lastSpace)}…`;
  }
  const cut = plain.slice(0, 240);
  return `${leading}${cut.slice(0, cut.lastIndexOf(" ") > 0 ? cut.lastIndexOf(" ") : 240)}…`;
}

export function AnswerPanel({ answer, onRetry }: AnswerPanelProps) {
  // Source number highlighted from the glossary ([2] → source 2).
  const [activeSource, setActiveSource] = useState<number | null>(null);

  if (answer.kind === "loading") {
    return <BakingLoader />;
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
        <TraceDetails
        key={answer.trace_id ?? "none"}
        traceId={answer.trace_id}
        label="Show the steps behind this answer"
      />
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

  function jumpToSource(number: number) {
    const item = document.getElementById(`source-${number}`);
    if (!item) return;
    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    item.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "nearest" });
    item.classList.remove("flash");
    // Restart the highlight animation even when the same source is chosen twice.
    void item.offsetWidth;
    item.classList.add("flash");
  }

  return (
    <div className="answer-reveal" key={answer.trace_id ?? answer.text.slice(0, 40)}>
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
          <SafeMarkdown>{answer.text}</SafeMarkdown>
        </div>
      )}
      {answer.kind === "answered" && answer.references.length > 0 && (
        <div className="references">
          <h3>Where this comes from</h3>
          <ul>
            {answer.references.map((reference, index) => (
              <li
                key={`${reference.chunk_id}-${reference.position}`}
                id={`source-${index + 1}`}
                className={activeSource === index + 1 ? "is-highlighted" : undefined}
                style={{ "--i": index } as CSSProperties}
              >
                <span className="reference-meta" title={reference.source}>
                  [{index + 1}] {documentTitle(reference.source)}
                  {documentCategory(reference.source)
                    ? ` · ${documentCategory(reference.source)}`
                    : ""}
                  {` · part ${reference.position + 1}`}
                </span>
                <span className="reference-quote">
                  “{cleanQuote(reference.quote, reference.position)}”
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {answer.kind === "answered" && answer.glossary.length > 0 && (
        <Glossary
          entries={answer.glossary}
          references={answer.references}
          onHighlight={setActiveSource}
          onJump={jumpToSource}
        />
      )}
      {answer.kind === "answered" && (
        <AnswerActions
          text={answer.text}
          references={answer.references}
          traceId={answer.trace_id}
        />
      )}
      {answer.retrieval && <RetrievalDetails retrieval={answer.retrieval} />}
      <TraceDetails
        key={answer.trace_id ?? "none"}
        traceId={answer.trace_id}
        label="Show the steps behind this answer"
      />
    </div>
  );
}

/** Terms used in the answer, each defined from a passage the answer cites. */
function Glossary({
  entries,
  references,
  onHighlight,
  onJump,
}: {
  entries: GlossaryEntry[];
  references: AnswerReference[];
  onHighlight: (number: number | null) => void;
  onJump: (number: number) => void;
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
                  <>
                    {" "}
                    <button
                      type="button"
                      className="glossary-source"
                      aria-label={`Show source ${number}`}
                      onMouseEnter={() => onHighlight(number)}
                      onMouseLeave={() => onHighlight(null)}
                      onFocus={() => onHighlight(number)}
                      onBlur={() => onHighlight(null)}
                      onClick={() => onJump(number)}
                    >
                      [{number}]
                    </button>
                  </>
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
                <SafeMarkdown>{chunk.text}</SafeMarkdown>
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
                <SafeMarkdown>{chunk.text}</SafeMarkdown>
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
