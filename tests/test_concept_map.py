import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend import concept_map, documents, graph_retrieval, rag_service, retrieval
from backend.graph_retrieval import _triple_signature
from backend.main import app
from backend.schemas import SourceChunk


def entity(name, kind):
    return {'name': name, 'entity_type': kind}


class ConceptMapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.graph_path = Path(self.temp.name) / 'graph.json'
        postroom = entity('postroom', 'SERVICE')
        messaging = entity('Messaging', 'TEAM')
        mailman = entity('mailman', 'SERVICE')
        self.triples = []
        edges = [
            (postroom, 'OWNED_BY', messaging),
            (entity('KST-5031', 'ERROR_CODE'), 'AFFECTS_SERVICE', mailman),
            (postroom, 'REPLACES', mailman),
            (entity('Identity', 'SERVICE'), 'OWNED_BY', entity('Identity', 'TEAM')),
            (postroom, 'OWNED_BY', messaging),
        ]
        for position, (subject, relation, object_) in enumerate(edges):
            self.triples.append({
                'subject': subject, 'relation': relation, 'object': object_,
                'chunk_id': retrieval.make_chunk_id('service-catalog.md', position),
                'evidence_quote': f'Original evidence {position}',
            })
        self.write_graph()
        self.enterContext(patch.object(graph_retrieval, 'GRAPH_FILE', self.graph_path))
        self.enterContext(patch.object(rag_service, 'APP_SETTINGS', rag_service.Settings(800, 80)))
        self.exclusions = self.enterContext(patch.object(concept_map, '_load_excluded_triples', return_value=set()))

    def write_graph(self):
        self.graph_path.write_text(json.dumps({
            'triples': self.triples,
            'statistics': {'chunk_size': 800, 'overlap': 80},
        }))

    def identifier(self, name, kind):
        return concept_map.concept_id(name, kind)

    def test_lists_all_typed_entities_deterministically(self):
        result = concept_map.list_concepts()
        self.assertEqual(len(result), 6)
        self.assertEqual([(c.name, c.type) for c in result], sorted(((c.name, c.type) for c in result), key=lambda x: (x[0].casefold(), x[1])))
        first = [c.model_dump() for c in result]
        self.triples.reverse()
        self.write_graph()
        self.assertEqual(first, [c.model_dump() for c in concept_map.list_concepts()])

    def test_case_insensitive_partial_search(self):
        self.assertEqual([c.name for c in concept_map.list_concepts('POST')], ['postroom'])
        self.assertEqual([c.name for c in concept_map.list_concepts('  messaging ')], ['Messaging'])

    def test_blank_search_lists_all_and_unmatched_search_is_empty(self):
        self.assertEqual(concept_map.list_concepts('  '), concept_map.list_concepts())
        self.assertEqual(concept_map.list_concepts('unknown'), [])

    def test_neighbourhood_preserves_directions_relations_and_provenance(self):
        result = concept_map.get_concept_neighbourhood(self.identifier('postroom', 'SERVICE'))
        outgoing = next(n for n in result.neighbours if n.relation == 'OWNED_BY')
        self.assertEqual(outgoing.concept.name, 'Messaging')
        self.assertEqual(outgoing.direction, 'outgoing')
        self.assertEqual(outgoing.chunk_ids, sorted([self.triples[0]['chunk_id'], self.triples[4]['chunk_id']]))
        incoming = next(n for n in result.neighbours if n.relation == 'AFFECTS_SERVICE')
        self.assertEqual(incoming.concept.name, 'KST-5031')
        self.assertEqual(incoming.direction, 'incoming')
        self.assertEqual(incoming.chunk_ids, [self.triples[1]['chunk_id']])
        self.assertEqual(set(result.model_dump()), {'concept', 'neighbours'})

    def test_reverse_neighbourhood_keeps_original_relation_label(self):
        result = concept_map.get_concept_neighbourhood(self.identifier('Messaging', 'TEAM'))
        self.assertEqual(len(result.neighbours), 1)
        self.assertEqual(result.neighbours[0].relation, 'OWNED_BY')
        self.assertEqual(result.neighbours[0].direction, 'incoming')

    def test_same_name_different_types_have_distinct_ids(self):
        concepts = concept_map.list_concepts('identity')
        self.assertEqual(len(concepts), 2)
        self.assertNotEqual(concepts[0].id, concepts[1].id)
        result = concept_map.get_concept_neighbourhood(self.identifier('Identity', 'SERVICE'))
        self.assertEqual(result.neighbours[0].concept.type, 'TEAM')

    def test_ids_follow_existing_case_insensitive_typed_identity(self):
        self.assertEqual(self.identifier('postroom', 'SERVICE'), self.identifier('POSTROOM', 'SERVICE'))
        self.assertNotEqual(self.identifier('Identity', 'SERVICE'), self.identifier('Identity', 'TEAM'))

    def test_alias_is_preserved_on_replaces_and_resolved_elsewhere(self):
        alias = concept_map.get_concept_neighbourhood(self.identifier('mailman', 'SERVICE'))
        self.assertEqual([(n.concept.name, n.relation, n.direction) for n in alias.neighbours], [('postroom', 'REPLACES', 'incoming')])
        canonical = concept_map.get_concept_neighbourhood(self.identifier('postroom', 'SERVICE'))
        self.assertTrue(any(n.relation == 'AFFECTS_SERVICE' for n in canonical.neighbours))

    def test_excluded_reviewed_triples_are_not_exposed(self):
        self.exclusions.return_value = {_triple_signature(self.triples[3])}
        self.assertEqual(concept_map.list_concepts('identity'), [])

    def test_unknown_concept_is_not_found(self):
        for identifier in ('', 'missing', self.identifier('missing', 'TEAM')):
            with self.subTest(identifier=identifier), self.assertRaises(concept_map.ConceptNotFoundError):
                concept_map.get_concept_neighbourhood(identifier)

    def test_missing_graph_has_safe_unavailable_error(self):
        self.graph_path.unlink()
        with self.assertRaisesRegex(concept_map.GraphUnavailableError, 'missing or invalid') as error:
            concept_map.list_concepts()
        self.assertNotIn(self.temp.name, str(error.exception))

    def test_malformed_graph_is_unavailable(self):
        self.graph_path.write_text('{broken json')
        with self.assertRaises(concept_map.GraphUnavailableError):
            concept_map.list_concepts()

    def test_empty_graph_returns_empty_list(self):
        self.triples = []
        self.write_graph()
        self.assertEqual(concept_map.list_concepts(), [])

    def test_mismatched_settings_reject_list_neighbourhood_and_evidence(self):
        rag_service.APP_SETTINGS.chunk_size = 400
        rag_service.APP_SETTINGS.overlap = 40
        for call in (
            lambda: concept_map.list_concepts(),
            lambda: concept_map.get_concept_neighbourhood(self.identifier('postroom', 'SERVICE')),
            lambda: concept_map.get_supporting_chunk(self.triples[0]['chunk_id']),
        ):
            with self.assertRaisesRegex(concept_map.GraphUnavailableError, 'rebuild'):
                call()

    def test_supporting_chunk_uses_kestrel_and_original_text(self):
        original = SourceChunk(id=self.triples[0]['chunk_id'], source='service-catalog.md', position=0, text='Original evidence 0', distance=0)
        with patch.object(rag_service, 'get_chunk_by_id', return_value=original) as get:
            result = concept_map.get_supporting_chunk(original.id)
        self.assertEqual(result, original)
        get.assert_called_once_with(original.id, dataset='kestrel')

    def test_missing_or_changed_evidence_is_unavailable(self):
        chunk_id = self.triples[0]['chunk_id']
        for value in (None, SourceChunk(id=chunk_id, source='service-catalog.md', position=0, text='Changed evidence', distance=0)):
            with patch.object(rag_service, 'get_chunk_by_id', return_value=value), self.assertRaises(concept_map.GraphUnavailableError):
                concept_map.get_supporting_chunk(chunk_id)

    def test_unrelated_chunk_cannot_be_presented_as_graph_evidence(self):
        with self.assertRaises(LookupError):
            concept_map.get_supporting_chunk(retrieval.make_chunk_id('other.md', 0))

    def test_reads_do_not_create_traces_or_call_gemini(self):
        with patch('backend.tracing.create_trace') as create, patch('backend.graph_extraction.client') as client:
            concept_map.list_concepts()
            concept_map.get_concept_neighbourhood(self.identifier('postroom', 'SERVICE'))
        create.assert_not_called()
        client.chat.completions.create.assert_not_called()

    def test_existing_endpoint_opens_graph_evidence_with_guard_enabled(self):
        chunk_id = self.triples[0]['chunk_id']
        original = SourceChunk(id=chunk_id, source='service-catalog.md', position=0, text='Original evidence 0', distance=0)
        with patch.object(rag_service, 'get_chunk_by_id', return_value=original):
            response = TestClient(app).get(f'/api/chunks/{chunk_id}?dataset=kestrel&graph_evidence=true')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['chunk']['text'], original.text)

    def test_graph_evidence_endpoint_rejects_mismatch_and_wrong_dataset(self):
        chunk_id = self.triples[0]['chunk_id']
        client = TestClient(app)
        self.assertEqual(client.get(f'/api/chunks/{chunk_id}?graph_evidence=true').status_code, 422)
        rag_service.APP_SETTINGS.chunk_size = 400
        rag_service.APP_SETTINGS.overlap = 40
        response = client.get(f'/api/chunks/{chunk_id}?dataset=kestrel&graph_evidence=true')
        self.assertEqual(response.status_code, 422)
        self.assertIn('rebuild', response.text)

    def test_optional_trace_records_counts_without_query_or_entity_labels(self):
        from tests.test_llm_tracing import FakeTrace
        trace = FakeTrace()
        concept_map.list_concepts('postroom', trace=trace)
        concept_map.get_concept_neighbourhood(self.identifier('postroom', 'SERVICE'), trace=trace)
        self.assertEqual(trace.spans[0].attributes, {'concept_count': 1})
        self.assertEqual(trace.spans[1].attributes, {'relationship_count': 3, 'supporting_chunk_count': 4})
        self.assertNotIn('postroom', str([s.attributes for s in trace.spans]))


class EvidenceLookupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.baking = self.root / 'baking'
        self.kestrel = self.root / 'kestrel'
        self.baking.mkdir()
        self.kestrel.mkdir()
        (self.baking / 'same.md').write_text('Baking original')
        (self.kestrel / 'same.md').write_text('Kestrel original')
        self.enterContext(patch.object(rag_service, 'DATASET_DIRECTORIES', {'baking': self.baking, 'kestrel': self.kestrel}))
        self.chunk_id = retrieval.make_chunk_id('same.md', 0)

    def collection(self, text):
        collection = MagicMock()
        collection.count.return_value = 1
        collection.get.return_value = {'ids': [self.chunk_id], 'documents': [text], 'metadatas': [{'source': 'same.md', 'position': 0}]}
        return collection

    def test_baking_is_default_and_kestrel_is_explicit_without_cross_dataset_fallback(self):
        collections = {'baking': self.collection('Baking chunk'), 'kestrel': self.collection('Kestrel chunk')}
        with patch.object(retrieval, 'get_collection', side_effect=lambda dataset: collections[dataset]):
            self.assertEqual(retrieval.get_chunk(self.chunk_id)['text'], 'Baking chunk')
            self.assertEqual(retrieval.get_chunk(self.chunk_id, dataset='kestrel')['text'], 'Kestrel chunk')

    def test_real_chroma_keeps_same_chunk_id_separate_between_datasets(self):
        import chromadb
        from backend import vector_store

        client = chromadb.EphemeralClient()
        with patch.object(vector_store, '_client', client):
            for dataset, text in [('baking', 'Baking evidence'), ('kestrel', 'Kestrel evidence')]:
                collection = vector_store.get_collection(dataset)
                collection.add(
                    ids=[self.chunk_id], documents=[text],
                    embeddings=[[1.0] + [0.0] * 383],
                    metadatas=[{'source': 'same.md', 'position': 0}],
                )
            self.assertEqual(retrieval.get_chunk(self.chunk_id)['text'], 'Baking evidence')
            self.assertEqual(retrieval.get_chunk(self.chunk_id, dataset='kestrel')['text'], 'Kestrel evidence')

    def test_missing_collection_and_unknown_chunk_return_none(self):
        collection = self.collection('unused')
        collection.count.return_value = 0
        with patch.object(retrieval, 'get_collection', return_value=collection):
            self.assertIsNone(retrieval.get_chunk(self.chunk_id, dataset='kestrel'))
            collection.count.return_value = 1
            collection.get.return_value = {'ids': []}
            self.assertIsNone(retrieval.get_chunk(self.chunk_id, dataset='kestrel'))

    def test_invalid_ids_and_datasets_are_rejected_before_collection_access(self):
        with patch.object(retrieval, 'get_collection') as get:
            for invalid in ('', '../secret', 'bad', 'a' * 12 + '::chunk_-001'):
                with self.assertRaises(ValueError):
                    retrieval.get_chunk(invalid)
            with self.assertRaises(ValueError):
                retrieval.get_chunk(self.chunk_id, dataset='other')
        get.assert_not_called()

    def test_service_refreshes_selected_dataset_at_active_settings(self):
        with patch.object(rag_service, 'ensure_index_current') as ensure, patch.object(retrieval, 'get_collection', return_value=self.collection('Kestrel chunk')):
            chunk = rag_service.get_chunk_by_id(self.chunk_id, dataset='kestrel')
        self.assertEqual(chunk.source, 'same.md')
        self.assertEqual(chunk.text, 'Kestrel chunk')
        ensure.assert_called_once_with('kestrel', rag_service.APP_SETTINGS.chunk_size, rag_service.APP_SETTINGS.overlap)

    def test_existing_chunk_endpoint_accepts_dataset_and_preserves_baking_default(self):
        original = SourceChunk(id=self.chunk_id, source='same.md', position=0, text='Kestrel chunk', distance=0)
        with patch('backend.main.get_chunk_by_id', return_value=original) as get:
            response = TestClient(app).get(f'/api/chunks/{self.chunk_id}?dataset=kestrel')
            self.assertEqual(response.status_code, 200, response.text)
            get.assert_called_with(self.chunk_id, dataset='kestrel')
            response = TestClient(app).get(f'/api/chunks/{self.chunk_id}')
            self.assertEqual(response.status_code, 200)
            get.assert_called_with(self.chunk_id, dataset='baking')

    def test_chunk_endpoint_unknown_and_invalid_ids(self):
        with patch.object(rag_service, 'ensure_index_current'), patch.object(retrieval, 'get_collection', return_value=self.collection('unused')) as get:
            get.return_value.get.return_value = {'ids': []}
            self.assertEqual(TestClient(app).get(f'/api/chunks/{self.chunk_id}?dataset=kestrel').status_code, 404)
            self.assertEqual(TestClient(app).get('/api/chunks/invalid?dataset=kestrel').status_code, 422)
            self.assertEqual(TestClient(app).get(f'/api/chunks/{self.chunk_id}?dataset=other').status_code, 422)

    def test_document_reader_returns_original_from_selected_corpus(self):
        self.assertEqual(rag_service.read_text_document('same.md'), 'Baking original')
        self.assertEqual(rag_service.read_text_document('same.md', dataset='kestrel'), 'Kestrel original')

    def test_nested_source_document_is_supported(self):
        (self.kestrel / 'nested').mkdir()
        (self.kestrel / 'nested/guide.txt').write_text('Nested evidence')
        self.assertEqual(rag_service.read_text_document('nested/guide.txt', dataset='kestrel'), 'Nested evidence')

    def test_document_reader_rejects_traversal_absolute_paths_and_unsupported_files(self):
        for invalid in ('../secret.md', 'nested/../../secret.md', '/etc/passwd', 'nested/../same.md', '..\\secret.md', 'same.pdf', ''):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                rag_service.read_text_document(invalid, dataset='kestrel')
        with self.assertRaises(ValueError):
            rag_service.read_text_document('same.md', dataset='other')

    def test_outside_quarantine_and_symlink_are_not_exposed(self):
        quarantine = self.root / 'quarantine'
        quarantine.mkdir()
        (quarantine / 'suspicious.md').write_text('Outside indexed directories')
        (self.kestrel / 'linked.md').symlink_to(quarantine / 'suspicious.md')
        with self.assertRaises(ValueError):
            rag_service.read_text_document('../quarantine/suspicious.md', dataset='kestrel')
        with self.assertRaises(ValueError):
            rag_service.read_text_document('linked.md', dataset='kestrel')
        with self.assertRaises(FileNotFoundError):
            rag_service.read_text_document('suspicious.md', dataset='kestrel')

    def test_missing_document_error_does_not_expose_filesystem_path(self):
        with self.assertRaises(FileNotFoundError) as error:
            rag_service.read_text_document('missing.md', dataset='kestrel')
        self.assertNotIn(str(self.root), str(error.exception))


if __name__ == '__main__':
    unittest.main()
