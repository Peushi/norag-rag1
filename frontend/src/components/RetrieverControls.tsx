import type { RetrieverName } from "../types/api";
import "../../styles/retriever-controls.css";

type RetrieverControlsProps = {
  dataset: "baking" | "kestrel";
  selectedRetrievers: RetrieverName[];
  onToggleRetriever: (retriever: RetrieverName) => void;
  includePathContext: boolean;
  onPathContextChange: (enabled: boolean) => void;
};

const RETRIEVERS: Array<{ id: RetrieverName; label: string; description: string }> = [
  {
    id: "dense",
    label: "Dense (embeddings)",
    description: "Find passages with similar meaning.",
  },
  {
    id: "bm25",
    label: "BM25 (keywords)",
    description: "Find passages that share important words.",
  },
  {
    id: "graph",
    label: "Concept graph",
    description: "Follow entity relationships across passages.",
  },
];

export function RetrieverControls({
  dataset,
  selectedRetrievers,
  onToggleRetriever,
  includePathContext,
  onPathContextChange,
}: RetrieverControlsProps) {
  return (
    <fieldset className="retriever-controls">
      <legend>Retrieval methods</legend>
      <p className="retriever-help">
        Enabled methods are combined by Reciprocal Rank Fusion. At least one
        method must be selected.
      </p>
      <div className="retriever-options">
        {RETRIEVERS.map((retriever) => {
          const graphUnavailable = retriever.id === "graph" && dataset !== "kestrel";
          return (
            <label
              className={`retriever-option${graphUnavailable ? " unavailable" : ""}`}
              key={retriever.id}
            >
              <input
                type="checkbox"
                checked={selectedRetrievers.includes(retriever.id)}
                disabled={graphUnavailable}
                onChange={() => onToggleRetriever(retriever.id)}
              />
              <span>
                <strong>{retriever.label}</strong>
                <small>
                  {graphUnavailable
                    ? "Available with the Kestrel corpus."
                    : retriever.description}
                </small>
              </span>
            </label>
          );
        })}
      </div>
      <label className="path-context-option">
        <input
          type="checkbox"
          checked={includePathContext}
          disabled={!selectedRetrievers.includes("graph")}
          onChange={(event) => onPathContextChange(event.target.checked)}
        />
        <span>
          <strong>Path as Context</strong>
          <small>
            Include graph relationships and their source passages in the
            language model prompt.
          </small>
        </span>
      </label>
    </fieldset>
  );
}
