export type DocumentSummary = {
  id: string;
  name: string;
  size_bytes: number;
};

export type AnswerReference = {
  chunk_id: string;
  source: string;
  position: number;
  quote: string;
};

export type RetrieverName = "dense" | "bm25" | "graph";

export type RetrieverContribution = {
  retriever: RetrieverName;
  rank: number;
  score?: number | null;
  score_type?: string | null;
};

export type FusedChunk = {
  id: string;
  text: string;
  source: string;
  position: number;
  final_rank: number;
  final_score: number;
  retrievers: RetrieverContribution[];
};

export type GraphEntity = string | {
  id?: string;
  name?: string;
  type?: string;
};

export type GraphEdge = {
  source_entity?: GraphEntity;
  relation?: string;
  target_entity?: GraphEntity;
  source?: GraphEntity;
  target?: GraphEntity;
  relation_type?: string;
  type?: string;
  supporting_chunk_ids?: string[];
  evidence_quote?: string;
  evidence_quotes?: string[];
};

export type GraphPath = {
  entities: GraphEntity[];
  edges: GraphEdge[];
  supporting_chunk_ids: string[];
};

export type GraphSupportingChunk = {
  id: string;
  text: string;
  source: string;
  position: number;
  rank: number;
  retriever: "graph";
  score?: number | null;
  score_type?: string | null;
};

export type PathContext = {
  paths: GraphPath[];
  supporting_chunks: Array<{
    chunk_id: string;
    source: string;
    position: number;
    text: string;
  }>;
};

export type AskRetrieval = {
  chunks: FusedChunk[];
  retrievers: RetrieverName[];
  graph_paths: GraphPath[];
  graph_supporting_chunks: GraphSupportingChunk[];
  path_context?: PathContext | null;
};

export type AskResponse = {
  status: "answered" | "not_found";
  answer: string;
  references: AnswerReference[];
  retrieval?: AskRetrieval | null;
};

export type Answer =
  | { kind: "empty"; text: string }
  | { kind: "loading" }
  | { kind: "error"; text: string }
  | { kind: "not_found"; text: string; retrieval?: AskRetrieval | null }
  | {
      kind: "answered";
      text: string;
      references: AnswerReference[];
      retrieval?: AskRetrieval | null;
    };

export function getApiErrorMessage(value: unknown, fallback: string): string {
  if (typeof value !== "object" || value === null || !("error" in value)) {
    return fallback;
  }

  const error = value.error;
  if (typeof error !== "object" || error === null || !("message" in error)) {
    return fallback;
  }

  return typeof error.message === "string" ? error.message : fallback;
}

export function isDocumentSummary(value: unknown): value is DocumentSummary {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  return (
    "id" in value &&
    typeof value.id === "string" &&
    "name" in value &&
    typeof value.name === "string" &&
    "size_bytes" in value &&
    typeof value.size_bytes === "number"
  );
}

export function isAskResponse(value: unknown): value is AskResponse {
  if (
    typeof value !== "object" ||
    value === null ||
    !("status" in value) ||
    (value.status !== "answered" && value.status !== "not_found") ||
    !("answer" in value) ||
    typeof value.answer !== "string" ||
    !("references" in value) ||
    !Array.isArray(value.references)
  ) {
    return false;
  }

  return value.references.every(
    (reference: unknown) =>
      typeof reference === "object" &&
      reference !== null &&
      "chunk_id" in reference &&
      typeof reference.chunk_id === "string" &&
      "source" in reference &&
      typeof reference.source === "string" &&
      "position" in reference &&
      typeof reference.position === "number" &&
      "quote" in reference &&
      typeof reference.quote === "string",
  ) && (
    !("retrieval" in value) ||
    value.retrieval === null ||
    value.retrieval === undefined ||
    isAskRetrieval(value.retrieval)
  );
}

function isAskRetrieval(value: unknown): value is AskRetrieval {
  if (
    typeof value !== "object" ||
    value === null ||
    !("retrievers" in value) ||
    !Array.isArray(value.retrievers) ||
    !value.retrievers.every(
      (retriever) =>
        retriever === "dense" || retriever === "bm25" || retriever === "graph",
    ) ||
    !("chunks" in value) ||
    !Array.isArray(value.chunks) ||
    !value.chunks.every(isFusedChunk) ||
    !("graph_paths" in value) ||
    !Array.isArray(value.graph_paths) ||
    !value.graph_paths.every(isGraphPath) ||
    !("graph_supporting_chunks" in value) ||
    !Array.isArray(value.graph_supporting_chunks) ||
    !value.graph_supporting_chunks.every(isGraphSupportingChunk)
  ) {
    return false;
  }

  return (
    !("path_context" in value) ||
    value.path_context === null ||
    value.path_context === undefined ||
    isPathContext(value.path_context)
  );
}

function isFusedChunk(value: unknown): value is FusedChunk {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  return (
    "id" in value &&
    typeof value.id === "string" &&
    "text" in value &&
    typeof value.text === "string" &&
    "source" in value &&
    typeof value.source === "string" &&
    "position" in value &&
    typeof value.position === "number" &&
    "final_rank" in value &&
    typeof value.final_rank === "number" &&
    "final_score" in value &&
    typeof value.final_score === "number" &&
    "retrievers" in value &&
    Array.isArray(value.retrievers) &&
    value.retrievers.every(isRetrieverContribution)
  );
}

function isRetrieverContribution(value: unknown): value is RetrieverContribution {
  return (
    typeof value === "object" &&
    value !== null &&
    "retriever" in value &&
    (value.retriever === "dense" ||
      value.retriever === "bm25" ||
      value.retriever === "graph") &&
    "rank" in value &&
    typeof value.rank === "number" &&
    (!("score" in value) ||
      value.score === null ||
      typeof value.score === "number") &&
    (!("score_type" in value) ||
      value.score_type === null ||
      typeof value.score_type === "string")
  );
}

function isGraphPath(value: unknown): value is GraphPath {
  return (
    typeof value === "object" &&
    value !== null &&
    "entities" in value &&
    Array.isArray(value.entities) &&
    value.entities.every(isGraphEntity) &&
    "edges" in value &&
    Array.isArray(value.edges) &&
    value.edges.every(isGraphEdge) &&
    "supporting_chunk_ids" in value &&
    Array.isArray(value.supporting_chunk_ids) &&
    value.supporting_chunk_ids.every((chunkId) => typeof chunkId === "string")
  );
}

function isGraphEntity(value: unknown): value is GraphEntity {
  if (typeof value === "string") {
    return true;
  }
  if (typeof value !== "object" || value === null) {
    return false;
  }
  return (
    (!("id" in value) || typeof value.id === "string") &&
    (!("name" in value) || typeof value.name === "string") &&
    (!("type" in value) || typeof value.type === "string")
  );
}

function isGraphEdge(value: unknown): value is GraphEdge {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const optionalStringProperties = [
    "relation",
    "relation_type",
    "type",
    "evidence_quote",
  ] as const;
  return (
    optionalStringProperties.every(
      (property) =>
        !(property in value) || typeof Reflect.get(value, property) === "string",
    ) &&
    ["source_entity", "target_entity", "source", "target"].every(
      (property) =>
        !(property in value) || isGraphEntity(Reflect.get(value, property)),
    ) &&
    (!("supporting_chunk_ids" in value) ||
      (Array.isArray(value.supporting_chunk_ids) &&
        value.supporting_chunk_ids.every(
          (chunkId) => typeof chunkId === "string",
        ))) &&
    (!("evidence_quotes" in value) ||
      (Array.isArray(value.evidence_quotes) &&
        value.evidence_quotes.every((quote) => typeof quote === "string")))
  );
}

function isGraphSupportingChunk(value: unknown): value is GraphSupportingChunk {
  return (
    typeof value === "object" &&
    value !== null &&
    "id" in value &&
    typeof value.id === "string" &&
    "text" in value &&
    typeof value.text === "string" &&
    "source" in value &&
    typeof value.source === "string" &&
    "position" in value &&
    typeof value.position === "number" &&
    "rank" in value &&
    typeof value.rank === "number" &&
    "retriever" in value &&
    value.retriever === "graph"
  );
}

function isPathContext(value: unknown): value is PathContext {
  return (
    typeof value === "object" &&
    value !== null &&
    "paths" in value &&
    Array.isArray(value.paths) &&
    value.paths.every(isGraphPath) &&
    "supporting_chunks" in value &&
    Array.isArray(value.supporting_chunks) &&
    value.supporting_chunks.every(
      (chunk) =>
        typeof chunk === "object" &&
        chunk !== null &&
        "chunk_id" in chunk &&
        typeof chunk.chunk_id === "string" &&
        "source" in chunk &&
        typeof chunk.source === "string" &&
        "position" in chunk &&
        typeof chunk.position === "number" &&
        "text" in chunk &&
        typeof chunk.text === "string",
    )
  );
}
