import { useEffect, useMemo, useState } from "react";
import { SafeMarkdown } from "./SafeMarkdown";
import {
  describeRequestError,
  getApiErrorDetail,
  readJson,
  type ConceptNeighbour,
  type ConceptNeighbourhood,
  type GraphConcept,
  type GraphStatus,
  type SourcePassage,
} from "../types/api";
import type { EvaluationDataset } from "../types/evaluations";
import { documentTitle } from "../utils/documentNames";
import { GraphBuildPanel } from "./GraphBuildPanel";
import { TraceDetails } from "./TraceDetails";

/** Plural, everyday names for the graph's entity types. */
const TYPE_LABELS: Record<string, string> = {
  ERROR_CODE: "Error codes",
  SERVICE: "Services",
  TEAM: "Teams",
  POLICY: "Policies",
  PRODUCT: "Products",
  PLAN: "Plans",
  FEATURE: "Features",
  ROLE: "Roles",
  CHANNEL: "Support channels",
  DISH: "Dishes",
  INGREDIENT: "Ingredients",
  EQUIPMENT: "Equipment",
  TECHNIQUE: "Techniques",
  PROBLEM: "Problems",
  CONDITION: "Conditions",
};

const TYPE_SINGULAR: Record<string, string> = {
  ERROR_CODE: "Error code",
  SERVICE: "Service",
  TEAM: "Team",
  POLICY: "Policy",
  PRODUCT: "Product",
  PLAN: "Plan",
  FEATURE: "Feature",
  ROLE: "Role",
  CHANNEL: "Support channel",
  DISH: "Dish",
  INGREDIENT: "Ingredient",
  EQUIPMENT: "Equipment",
  TECHNIQUE: "Technique",
  PROBLEM: "Problem",
  CONDITION: "Condition",
};

/** How each relation reads from the open concept's side: [outgoing, incoming]. */
const RELATION_PHRASES: Record<string, [string, string]> = {
  HANDLED_BY: ["is handled by", "handles"],
  OWNED_BY: ["is owned by", "owns"],
  ESCALATES_TO: ["escalates to", "receives escalations from"],
  HAS_CHANNEL: ["can be reached through", "is a channel for"],
  REPLACES: ["replaces", "is replaced by"],
  GOVERNED_BY: ["is governed by", "governs"],
  SUPPORTS: ["supports", "is supported by"],
  INCLUDES: ["includes", "is included in"],
  REQUIRES: ["requires", "is required by"],
  AFFECTS_SERVICE: ["affects", "is affected by"],
  HAS_CAUSE: ["is caused by", "causes"],
  RESOLVED_BY: ["is resolved by", "resolves"],
  CAUSES: ["causes", "is caused by"],
  FIXES: ["fixes", "is fixed by"],
  PREVENTS: ["prevents", "is prevented by"],
  USES: ["uses", "is used for"],
  AFFECTS: ["affects", "is affected by"],
  PART_OF: ["is part of", "includes"],
  SUBSTITUTES_FOR: ["can replace", "can be replaced by"],
};

function relationPhrase(neighbour: ConceptNeighbour): string {
  const phrases = RELATION_PHRASES[neighbour.relation];
  if (!phrases) {
    return neighbour.relation.toLowerCase().replace(/_/g, " ");
  }
  return neighbour.direction === "outgoing" ? phrases[0] : phrases[1];
}

/** Turn an API error into something a reader can act on. */
function conceptError(data: unknown, fallback: string): string {
  const detail = getApiErrorDetail(data);
  if (detail?.code === "GRAPH_UNAVAILABLE") {
    return "The concept map was built with different passage settings than your “Search options” now use. Set them back (800 and 80 by default), or update the map of your documents.";
  }
  return detail?.message || fallback;
}

type GraphBuild = {
  status: GraphStatus | null;
  isStarting: boolean;
  startError: { message: string; traceId: string | null } | null;
  startBuild: () => void;
};

type ConceptMapProps = {
  dataset: EvaluationDataset;
  onAskAbout: (concept: GraphConcept) => void;
  /** For the user's documents: the graph's state and how to build it. */
  build?: GraphBuild;
};

const COPY: Record<EvaluationDataset, { intro: string; placeholder: string }> = {
  kestrel: {
    intro: "How the sample’s services, teams, error codes and policies connect, with the passage behind each link.",
    placeholder: "For example: KST-5031, Billing, postroom",
  },
  baking: {
    intro: "How the dishes, ingredients, techniques and problems in your documents connect, with the passage behind each link.",
    placeholder: "For example: dough, butter, spreading",
  },
};

/** Concept explorer: search concepts, open one, follow its relationships to their sources. */
export function ConceptMap({ dataset, onAskAbout, build }: ConceptMapProps) {
  const notBuiltYet = build !== undefined && build.status !== null && !build.status.built;
  const [concepts, setConcepts] = useState<GraphConcept[]>([]);
  const [listError, setListError] = useState("");
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [query, setQuery] = useState("");
  const [path, setPath] = useState<GraphConcept[]>([]);
  const [neighbourhood, setNeighbourhood] = useState<ConceptNeighbourhood | null>(null);
  const [openError, setOpenError] = useState<{ message: string; traceId: string | null } | null>(null);
  const [isOpening, setIsOpening] = useState(false);

  async function loadConcepts() {
    setIsLoadingList(true);
    try {
      const response = await fetch(`/api/concepts?dataset=${dataset}`);
      const data = await readJson(response);
      if (!response.ok) {
        throw new Error(conceptError(data, "The concept map couldn’t be loaded."));
      }
      const rows =
        typeof data === "object" && data !== null && "concepts" in data
          ? data.concepts
          : null;
      if (!Array.isArray(rows)) {
        throw new Error("The server returned an unexpected concept list.");
      }
      setConcepts(rows as GraphConcept[]);
      setListError("");
    } catch (error) {
      setListError(
        describeRequestError(error, "The concept map couldn’t be loaded."),
      );
    } finally {
      setIsLoadingList(false);
    }
  }

  useEffect(() => {
    if (notBuiltYet || (build !== undefined && build.status === null)) {
      setIsLoadingList(false);
      return;
    }
    void loadConcepts();
    // Reload when a build of the user's graph finishes.
  }, [dataset, notBuiltYet, build?.status?.built_at]);

  async function openConcept(concept: GraphConcept, mode: "push" | "back" | "root") {
    setIsOpening(true);
    setOpenError(null);
    try {
      const response = await fetch(
        `/api/concepts/${encodeURIComponent(concept.id)}?dataset=${dataset}`,
      );
      const data = await readJson(response);
      if (!response.ok) {
        setOpenError({
          message: conceptError(data, `“${concept.name}” couldn’t be opened.`),
          traceId: response.headers.get("x-trace-id"),
        });
        return;
      }
      setNeighbourhood(data as ConceptNeighbourhood);
      setPath((current) =>
        mode === "root"
          ? [concept]
          : mode === "back"
            ? current.slice(0, -1)
            : [...current, concept],
      );
    } catch {
      setOpenError({
        message: "BakeFix can’t reach its server. Make sure the backend is running, then try again.",
        traceId: null,
      });
    } finally {
      setIsOpening(false);
    }
  }

  function closeConcept() {
    setNeighbourhood(null);
    setPath([]);
    setOpenError(null);
  }

  const grouped = useMemo(() => {
    const search = query.trim().toLowerCase();
    const groups = new Map<string, GraphConcept[]>();
    for (const concept of concepts) {
      if (search && !concept.name.toLowerCase().includes(search)) {
        continue;
      }
      const list = groups.get(concept.type) ?? [];
      list.push(concept);
      groups.set(concept.type, list);
    }
    return [...groups.entries()].sort(([a], [b]) =>
      (TYPE_LABELS[a] ?? a).localeCompare(TYPE_LABELS[b] ?? b),
    );
  }, [concepts, query]);

  const previous = path.length > 1 ? path[path.length - 2] : null;

  return (
    <aside className="card concept-map" aria-labelledby="concept-map-title">
      <div className="section-heading">
        <span className="section-icon" aria-hidden="true">
          ◎
        </span>
        <div>
          <h2 id="concept-map-title">Concept map</h2>
          <p>{COPY[dataset].intro}</p>
        </div>
      </div>

      {build?.status && (
        <GraphBuildPanel
          status={build.status}
          isStarting={build.isStarting}
          startError={build.startError}
          onBuild={build.startBuild}
        />
      )}

      {notBuiltYet ? null : neighbourhood ? (
        <div className="concept-detail">
          <div className="concept-nav">
            <button type="button" className="back-to-ask" onClick={closeConcept}>
              <span aria-hidden="true">←</span> All concepts
            </button>
            {previous && (
              <button
                type="button"
                className="back-to-ask"
                disabled={isOpening}
                onClick={() => void openConcept(previous, "back")}
              >
                <span aria-hidden="true">←</span> Back to {previous.name}
              </button>
            )}
          </div>

          <p className="concept-type">
            {TYPE_SINGULAR[neighbourhood.concept.type] ?? neighbourhood.concept.type}
          </p>
          <h3 className="concept-name">{neighbourhood.concept.name}</h3>

          <button
            type="button"
            className="button secondary concept-ask"
            onClick={() => onAskAbout(neighbourhood.concept)}
          >
            Ask about {neighbourhood.concept.name}
          </button>

          {openError && <ConceptError error={openError} />}

          {neighbourhood.neighbours.length === 0 ? (
            <p className="concept-empty">No relationships were extracted for this concept.</p>
          ) : (
            <ul className="concept-relations" aria-busy={isOpening}>
              {neighbourhood.neighbours.map((neighbour) => (
                <RelationRow
                  key={`${neighbour.relation}-${neighbour.direction}-${neighbour.concept.id}`}
                  dataset={dataset}
                  subject={neighbourhood.concept}
                  neighbour={neighbour}
                  disabled={isOpening}
                  onOpen={(concept) => void openConcept(concept, "push")}
                />
              ))}
            </ul>
          )}

          <TraceDetails key={neighbourhood.trace_id} traceId={neighbourhood.trace_id} />
        </div>
      ) : (
        <div className="concept-browser">
          <label className="concept-search" htmlFor="concept-search">
            Find a concept
            <input
              id="concept-search"
              type="search"
              value={query}
              placeholder={COPY[dataset].placeholder}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>

          {openError && <ConceptError error={openError} />}

          {isLoadingList ? (
            <p className="concept-empty" role="status">Loading the concept map…</p>
          ) : listError ? (
            <div className="library-error" role="alert">
              <p>{listError}</p>
              <button type="button" className="button secondary" onClick={() => void loadConcepts()}>
                Try again
              </button>
            </div>
          ) : grouped.length === 0 ? (
            <p className="concept-empty">
              {concepts.length === 0
                ? "The concept map is empty."
                : `No concept matches “${query.trim()}”.`}
            </p>
          ) : (
            grouped.map(([type, items]) => (
              <section className="concept-group" key={type}>
                <h3>{TYPE_LABELS[type] ?? type}</h3>
                <div className="concept-chips">
                  {items.map((concept) => (
                    <button
                      key={concept.id}
                      type="button"
                      className="example-question"
                      disabled={isOpening}
                      onClick={() => void openConcept(concept, "root")}
                    >
                      {concept.name}
                    </button>
                  ))}
                </div>
              </section>
            ))
          )}
        </div>
      )}
    </aside>
  );
}

function ConceptError({ error }: { error: { message: string; traceId: string | null } }) {
  return (
    <div className="indexing-activity error" role="alert">
      <p>{error.message}</p>
      <TraceDetails key={error.traceId ?? "none"} traceId={error.traceId} />
    </div>
  );
}

function RelationRow({
  dataset,
  subject,
  neighbour,
  disabled,
  onOpen,
}: {
  dataset: EvaluationDataset;
  subject: GraphConcept;
  neighbour: ConceptNeighbour;
  disabled: boolean;
  onOpen: (concept: GraphConcept) => void;
}) {
  const [showEvidence, setShowEvidence] = useState(false);
  const count = neighbour.chunk_ids.length;

  return (
    <li className="concept-relation">
      <p>
        <span className="concept-subject">{subject.name}</span>{" "}
        <span className="concept-phrase">{relationPhrase(neighbour)}</span>{" "}
        <button
          type="button"
          className="concept-link"
          disabled={disabled}
          onClick={() => onOpen(neighbour.concept)}
        >
          {neighbour.concept.name}
        </button>
      </p>
      <button
        type="button"
        className="concept-evidence-toggle"
        aria-expanded={showEvidence}
        onClick={() => setShowEvidence((open) => !open)}
      >
        {showEvidence
          ? "Hide source"
          : count === 1
            ? "Show the source passage"
            : `Show the ${count} source passages`}
      </button>
      {showEvidence && (
        <div className="concept-evidence">
          {neighbour.chunk_ids.map((chunkId) => (
            <EvidencePassage key={chunkId} chunkId={chunkId} dataset={dataset} />
          ))}
        </div>
      )}
    </li>
  );
}

/** One passage a relationship was extracted from, with a way to read the whole document. */
function EvidencePassage({ chunkId, dataset }: { chunkId: string; dataset: EvaluationDataset }) {
  const [passage, setPassage] = useState<SourcePassage | null>(null);
  const [error, setError] = useState("");
  const [documentText, setDocumentText] = useState<string | null>(null);
  const [documentError, setDocumentError] = useState("");
  const [isLoadingDocument, setIsLoadingDocument] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const response = await fetch(
          `/api/chunks/${encodeURIComponent(chunkId)}?dataset=${dataset}&graph_evidence=true`,
        );
        const data = await readJson(response);
        if (!response.ok) {
          throw new Error(conceptError(data, "This source passage couldn’t be loaded."));
        }
        const chunk =
          typeof data === "object" && data !== null && "chunk" in data ? data.chunk : null;
        if (!cancelled) {
          setPassage(chunk as SourcePassage);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(
            describeRequestError(loadError, "This source passage couldn’t be loaded."),
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [chunkId, dataset]);

  async function toggleDocument() {
    if (documentText !== null) {
      setDocumentText(null);
      return;
    }
    if (!passage) {
      return;
    }
    setIsLoadingDocument(true);
    setDocumentError("");
    try {
      const params = new URLSearchParams({ document_id: passage.source, dataset });
      const response = await fetch(`/api/document-text?${params.toString()}`);
      const data = await readJson(response);
      if (!response.ok) {
        throw new Error(conceptError(data, "This document couldn’t be opened."));
      }
      const text =
        typeof data === "object" && data !== null && "text" in data ? data.text : null;
      setDocumentText(typeof text === "string" ? text : "");
    } catch (loadError) {
      setDocumentError(
        describeRequestError(loadError, "This document couldn’t be opened."),
      );
    } finally {
      setIsLoadingDocument(false);
    }
  }

  if (error) {
    return <p className="error">{error}</p>;
  }
  if (!passage) {
    return <p className="concept-empty" role="status">Loading the source passage…</p>;
  }

  return (
    <article className="concept-passage">
      <span className="reference-meta">
        {dataset === "baking" ? documentTitle(passage.source) : passage.source} · part{" "}
        {passage.position + 1}
      </span>
      <div className="fused-chunk-text">
        <SafeMarkdown>{passage.text}</SafeMarkdown>
      </div>
      <button
        type="button"
        className="concept-evidence-toggle"
        aria-expanded={documentText !== null}
        disabled={isLoadingDocument}
        onClick={() => void toggleDocument()}
      >
        {isLoadingDocument
          ? "Opening…"
          : documentText !== null
            ? "Close the document"
            : `Read the whole document (${passage.source})`}
      </button>
      {documentError && <p className="error">{documentError}</p>}
      {documentText !== null && (
        <div className="concept-document" tabIndex={0} aria-label={`Full text of ${passage.source}`}>
          <SafeMarkdown>{documentText}</SafeMarkdown>
        </div>
      )}
    </article>
  );
}
