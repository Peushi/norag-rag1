import json
import re
from collections import defaultdict
from pathlib import Path

from backend.chunking import chunk_text
from backend.retrieval import make_chunk_id
from backend.entity_resolution import resolve_entity, resolve_graph_triples


PROJECT_ROOT = Path(__file__).resolve().parent.parent
KESTREL_DOCS = PROJECT_ROOT / "kestrel-kb" / "docs"
GRAPH_FILE = PROJECT_ROOT / "kestrel-kb" / "graph" / "graph.json"
QUALITY_FILE = PROJECT_ROOT / "kestrel-kb" / "graph" / "triple_quality_review.json"
# Graphs built from the user's own documents: local runtime data, like traces.
USER_GRAPH_ROOT = PROJECT_ROOT / ".bakefix" / "graphs"
BUILDABLE_DATASETS = {"baking"}


def graph_file(dataset: str = "kestrel") -> Path:
    """Kestrel uses its committed, reviewed graph; other corpora use a built one.

    Read at call time so tests can point GRAPH_FILE / USER_GRAPH_ROOT elsewhere.
    """
    if dataset == "kestrel":
        return GRAPH_FILE
    if dataset not in BUILDABLE_DATASETS:
        raise ValueError(f"No concept graph for dataset: {dataset}")
    return USER_GRAPH_ROOT / dataset / "graph.json"


def graph_exists(dataset: str = "kestrel") -> bool:
    return graph_file(dataset).exists()


def _entity_key(entity):
    return (
        entity["name"].casefold(),
        entity["entity_type"],
    )


def _triple_signature(triple):
    """Create a stable identity for matching reviewed triples."""
    return (
        triple["subject"]["name"].casefold(),
        triple["subject"]["entity_type"],
        triple["relation"],
        triple["object"]["name"].casefold(),
        triple["object"]["entity_type"],
        triple["chunk_id"],
    )


def _load_graph(dataset: str = "kestrel"):
    path = graph_file(dataset)
    if not path.exists():
        raise FileNotFoundError(f"Graph not found: {path}")

    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _load_excluded_triples(dataset: str = "kestrel"):
    """Exclude only triples explicitly reviewed as wrong or unsupported."""
    # Only the committed Kestrel graph has a manual quality review.
    if dataset != "kestrel" or not QUALITY_FILE.exists():
        return set()

    with QUALITY_FILE.open(encoding="utf-8") as file:
        review_data = json.load(file)

    excluded = set()

    for result in review_data.get("results", []):
        if result.get("review") in {"wrong", "unsupported"}:
            excluded.add(_triple_signature(result["triple"]))

    return excluded


def _load_chunks(dataset, chunk_size, overlap):
    """Recreate a corpus's chunks (same IDs as search) at the graph's settings."""
    if dataset == "kestrel":
        return _load_kestrel_chunks(chunk_size, overlap)
    from backend import retrieval
    from backend.documents import load_documents

    chunk_lookup = {}
    for document in load_documents(retrieval.DATASET_DIRECTORIES[dataset]):
        for chunk in chunk_text(document["text"], chunk_size=chunk_size, overlap=overlap):
            chunk_id = make_chunk_id(document["source"], chunk["position"])
            chunk_lookup[chunk_id] = {
                "id": chunk_id,
                "text": chunk["text"],
                "source": document["source"],
                "position": chunk["position"],
            }
    return chunk_lookup


def _load_kestrel_chunks(chunk_size, overlap):
    """Recreate Kestrel chunks using the graph's original chunk settings."""
    if not KESTREL_DOCS.exists():
        raise FileNotFoundError(f"Kestrel documents not found: {KESTREL_DOCS}")

    chunk_lookup = {}

    documents = sorted(
        path for path in KESTREL_DOCS.rglob("*")
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}
    )

    for document_path in documents:
        text = document_path.read_text(encoding="utf-8")
        source = document_path.relative_to(KESTREL_DOCS).as_posix()

        chunks = chunk_text(
            text,
            chunk_size=chunk_size,
            overlap=overlap,
        )

        for chunk in chunks:
            chunk_id = make_chunk_id(source, chunk["position"])

            chunk_lookup[chunk_id] = {
                "id": chunk_id,
                "text": chunk["text"],
                "source": source,
                "position": chunk["position"],
            }

    return chunk_lookup


GENERIC_ENTITY_NAMES = {
    "team",
    "plan",
    "owner",
    "service",
    "policy",
    "product",
    "role",
    "channel",
}


def _entity_matches_question(question, name):
    """Avoid matching generic entity names used as ordinary words."""
    if name.casefold().strip() in GENERIC_ENTITY_NAMES:
        return False

    pattern = r"(?<!\w)" + re.escape(name) + r"(?!\w)"
    return re.search(pattern, question, flags=re.IGNORECASE) is not None


# Words that carry no meaning for matching a concept to a question.
STOPWORDS = {
    "a", "an", "and", "are", "at", "be", "but", "by", "can", "did", "didn", "do", "does",
    "doesn", "for", "from", "has", "have", "how", "i", "in", "is", "it", "its", "keep",
    "keeps", "my", "no", "not", "of", "on", "or", "so", "the", "their", "this", "to",
    "too", "very", "was", "what", "when", "why", "will", "with", "won", "your",
}
_SUFFIXES = ("ings", "ing", "ies", "es", "ed", "s")


def _word_stem(word):
    """A light stemmer: 'spreading' → 'spread', 'cookies' → 'cook', 'rising' → 'ris'."""
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def _content_stems(text):
    words = re.findall(r"[a-z0-9]+", text.casefold())
    return [_word_stem(word) for word in words if word not in STOPWORDS]


def _stems_match(a, b):
    return a == b or (min(len(a), len(b)) >= 3 and (a.startswith(b) or b.startswith(a)))


def _entity_words_in_question(question, name):
    """Every meaningful word of the concept appears in the question, in any form.

    Kitchen concepts are phrases ("cookies spreading", "dough not rising") that
    people rarely type word for word ("why do my cookies keep spreading?").
    """
    if name.casefold().strip() in GENERIC_ENTITY_NAMES:
        return False
    name_stems = _content_stems(name)
    question_stems = _content_stems(question)
    return bool(name_stems) and all(
        any(_stems_match(stem, word) for word in question_stems) for stem in name_stems
    )


def _find_question_entities(question, triples, dataset="kestrel"):
    """Find mentioned entities, preferring specific names over shorter overlaps.

    Kestrel keeps exact-name matching (error codes and service names are typed
    as written, and its evaluation results depend on it); other corpora also
    match word forms.
    """
    entities = {}

    for triple in triples:
        for entity in (triple["subject"], triple["object"]):
            entities[_entity_key(entity)] = entity

    matched = []

    for entity in entities.values():
        if _entity_matches_question(question, entity["name"]) or (
            dataset != "kestrel" and _entity_words_in_question(question, entity["name"])
        ):
            matched.append(entity)

    # If a specific versioned name matches, don't also match its generic name.
    filtered = []

    for entity in matched:
        name = entity["name"]

        shadowed = any(
            other["entity_type"] == entity["entity_type"]
            and len(other["name"]) > len(name)
            and _entity_matches_question(other["name"], name)
            for other in matched
        )

        if not shadowed:
            filtered.append(entity)

    result = {}

    for entity in filtered:
        result[_entity_key(entity)] = entity
        if dataset != "kestrel":
            continue

        canonical = resolve_entity(
            entity["name"],
            entity["entity_type"],
        )
        result[_entity_key(canonical)] = canonical

    return list(result.values())


def _build_paths(triples, matched_entities, max_hops):
    """Find one-hop and two-hop paths from entities mentioned in a question."""
    adjacency = defaultdict(list)

    for index, triple in enumerate(triples):
        subject_key = _entity_key(triple["subject"])
        object_key = _entity_key(triple["object"])

        adjacency[subject_key].append((index, object_key))
        adjacency[object_key].append((index, subject_key))

    entity_lookup = {}

    for triple in triples:
        entity_lookup[_entity_key(triple["subject"])] = triple["subject"]
        entity_lookup[_entity_key(triple["object"])] = triple["object"]

    paths = []
    seen_paths = set()

    for start_entity in matched_entities:
        start_key = _entity_key(start_entity)

        # Current entity, visited entities, edge indexes, used edge indexes.
        stack = [(start_key, [start_key], [], set())]

        while stack:
            current, visited_nodes, edge_indexes, used_edges = stack.pop()

            if len(edge_indexes) >= max_hops:
                continue

            for edge_index, next_node in adjacency[current]:
                if edge_index in used_edges or next_node in visited_nodes:
                    continue

                new_edges = edge_indexes + [edge_index]
                new_nodes = visited_nodes + [next_node]

                signature = tuple(new_edges)

                if signature not in seen_paths:
                    seen_paths.add(signature)

                    path_triples = [triples[i] for i in new_edges]
                    supporting_ids = list(dict.fromkeys(
                        triple["chunk_id"] for triple in path_triples
                    ))

                    paths.append({
                        "hop_count": len(new_edges),
                        "entities": [
                            entity_lookup[node] for node in new_nodes
                        ],
                        "edges": path_triples,
                        "supporting_chunk_ids": supporting_ids,
                    })

                stack.append((
                    next_node,
                    new_nodes,
                    new_edges,
                    used_edges | {edge_index},
                ))

    return paths


def retrieve_graph(
    question,
    top_k=5,
    selected_documents=None,
    max_hops=2,
    dataset="kestrel",
):
    """
    Retrieve evidence through graph entities and relationships.

    Returns ranked chunks, graph paths, and matched entities.
    """
    if not question or not question.strip():
        raise ValueError("Question cannot be empty")

    if top_k < 1:
        raise ValueError("top_k must be at least 1")

    if max_hops not in (1, 2):
        raise ValueError("max_hops must be 1 or 2")

    if selected_documents is not None and not selected_documents:
        return {
            "chunks": [],
            "paths": [],
            "matched_entities": [],
        }

    graph_data = _load_graph(dataset)
    raw_triples = graph_data.get("triples", [])

    excluded = _load_excluded_triples(dataset)

    # Filter using the original triples before applying entity resolution.
    eligible_triples = [
        triple for triple in raw_triples
        if _triple_signature(triple) not in excluded
    ]

    # Resolve aliases for normal relationships while preserving REPLACES.
    # The alias list was written for Kestrel; built graphs are used as extracted.
    triples = (
        resolve_graph_triples(eligible_triples) if dataset == "kestrel" else eligible_triples
    )

    matched_entities = _find_question_entities(
        question,
        eligible_triples,
        dataset,
    )

    if not matched_entities:
        return {
            "chunks": [],
            "paths": [],
            "matched_entities": [],
        }

    paths = _build_paths(
        triples,
        matched_entities,
        max_hops,
    )

    statistics = graph_data.get("statistics", {})

    chunk_lookup = _load_chunks(
        dataset,
        chunk_size=statistics.get("chunk_size", 800),
        overlap=statistics.get("overlap", 80),
    )

    # Score each supporting chunk using its best path.
    chunk_scores = {}

    for path in paths:
        score = 1.0 / path["hop_count"]

        for chunk_id in path["supporting_chunk_ids"]:
            chunk_scores[chunk_id] = max(
                chunk_scores.get(chunk_id, 0.0),
                score,
            )

    ranked_ids = sorted(
        chunk_scores,
        key=lambda chunk_id: (
            -chunk_scores[chunk_id],
            chunk_id,
        ),
    )

    chunks = []

    for chunk_id in ranked_ids:
        chunk = chunk_lookup.get(chunk_id)

        if chunk is None:
            continue

        if (
            selected_documents is not None
            and chunk["source"] not in selected_documents
        ):
            continue

        chunks.append({
            **chunk,
            "rank": len(chunks) + 1,
            "retriever": "graph",
            "graph_score": chunk_scores[chunk_id],
        })

        if len(chunks) >= top_k:
            break

    selected_ids = {chunk["id"] for chunk in chunks}

    relevant_paths = [
        path for path in paths
        if selected_ids.intersection(path["supporting_chunk_ids"])
    ]

    return {
        "chunks": chunks,
        "paths": relevant_paths,
        "matched_entities": matched_entities,
    }
