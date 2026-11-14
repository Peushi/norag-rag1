"""Read-only Concept Map services for Sasha's API/frontend integration."""

import hashlib
import json
from contextlib import nullcontext

from backend import rag_service
from backend.entity_resolution import resolve_graph_triples
from backend.graph_retrieval import _load_excluded_triples, _load_graph, _triple_signature
from backend.graph_schemas import (
    ConceptNeighbour,
    ConceptNeighbourhood,
    GraphConcept,
    GraphTriple,
)
from backend.llm_service import TraceContext
from backend.retrieval import validate_chunk_id
from backend.schemas import SourceChunk


class GraphUnavailableError(ValueError):
    """The saved graph or its evidence cannot currently be used safely."""


class ConceptNotFoundError(LookupError):
    """No concept in the saved graph has the requested ID."""


def concept_id(name: str, entity_type: str) -> str:
    """V3 has no stored entity IDs: derive one from its typed entity identity."""
    identity = json.dumps([entity_type, name.casefold()], ensure_ascii=False)
    return 'concept_' + hashlib.sha256(identity.encode('utf-8')).hexdigest()


def _view():
    try:
        graph = _load_graph()
        if not isinstance(graph, dict):
            raise ValueError('Invalid graph structure')
        statistics = graph.get('statistics', {})
        if not isinstance(statistics, dict):
            raise ValueError('Invalid graph statistics')
        graph_settings = (statistics.get('chunk_size', 800), statistics.get('overlap', 80))
        active = (rag_service.APP_SETTINGS.chunk_size, rag_service.APP_SETTINGS.overlap)
        if active != graph_settings:
            raise GraphUnavailableError(
                f'Graph requires chunk_size={graph_settings[0]}, overlap={graph_settings[1]}; '
                'use matching settings or rebuild the graph before exploring evidence.'
            )
        excluded = _load_excluded_triples()
        raw = [GraphTriple.model_validate(t).model_dump() for t in graph.get('triples', [])]
        eligible = [t for t in raw if _triple_signature(t) not in excluded]
        triples = resolve_graph_triples(eligible)
    except GraphUnavailableError:
        raise
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise GraphUnavailableError('Kestrel graph data is missing or invalid.') from exc

    # Preserve typed identities, aliases on REPLACES edges, and deterministic labels.
    entities = sorted(
        (e for t in triples for e in (t['subject'], t['object'])),
        key=lambda e: (e['entity_type'], e['name'].casefold(), e['name']),
    )
    concepts = {}
    for entity in entities:
        identifier = concept_id(entity['name'], entity['entity_type'])
        concepts.setdefault(identifier, GraphConcept(
            id=identifier, name=entity['name'], type=entity['entity_type'],
        ))
    return concepts, triples


def list_concepts(query: str | None = None, *, trace: TraceContext | None = None) -> list[GraphConcept]:
    """List/search eligible Kestrel concepts; no trace is persisted by default."""
    with (trace.span('concept_search') if trace is not None else nullcontext()) as span:
        concepts, _ = _view()
        search = (query or '').strip().casefold()
        result = sorted(
            (c for c in concepts.values() if search in c.name.casefold()),
            key=lambda c: (c.name.casefold(), c.type, c.id),
        )
        if span is not None:
            span.set_attribute('concept_count', len(result))
        return result


def get_concept_neighbourhood(identifier: str, *, trace: TraceContext | None = None) -> ConceptNeighbourhood:
    """Return original edge directions and deduplicated supporting chunk IDs."""
    with (trace.span('concept_neighbourhood') if trace is not None else nullcontext()) as span:
        concepts, triples = _view()
        if identifier not in concepts:
            raise ConceptNotFoundError('Concept not found.')
        grouped = {}
        for triple in triples:
            subject = concept_id(triple['subject']['name'], triple['subject']['entity_type'])
            object_id = concept_id(triple['object']['name'], triple['object']['entity_type'])
            for own, other, direction in (
                (subject, object_id, 'outgoing'), (object_id, subject, 'incoming'),
            ):
                if own == identifier:
                    key = (other, triple['relation'], direction)
                    grouped.setdefault(key, set()).add(triple['chunk_id'])
        neighbours = [
            ConceptNeighbour(concept=concepts[other], relation=relation,
                             direction=direction, chunk_ids=sorted(ids))
            for (other, relation, direction), ids in grouped.items()
        ]
        neighbours.sort(key=lambda n: (n.concept.name.casefold(), n.concept.type, n.relation, n.direction))
        if span is not None:
            span.set_attribute('relationship_count', len(neighbours))
            span.set_attribute('supporting_chunk_count', len({c for n in neighbours for c in n.chunk_ids}))
        return ConceptNeighbourhood(concept=concepts[identifier], neighbours=neighbours)


def get_supporting_chunk(chunk_id: str) -> SourceChunk:
    """Open graph evidence only with matching settings and its original quote."""
    validate_chunk_id(chunk_id)
    _, triples = _view()
    supporting = [t for t in triples if t['chunk_id'] == chunk_id]
    if not supporting:
        raise LookupError('Graph supporting chunk not found.')
    chunk = rag_service.get_chunk_by_id(chunk_id, dataset='kestrel')
    if chunk is None or any(t['evidence_quote'] not in chunk.text for t in supporting):
        raise GraphUnavailableError('Graph evidence is missing or changed; rebuild the graph before using it.')
    return chunk
