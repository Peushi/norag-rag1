import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend import documents, graph_index, retrieval, rag_service, tracing
from backend.main import app


class IndexingTraceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.corpus = self.root / 'corpus'
        self.corpus.mkdir()
        self.private = 'Contact private.person@example.com. API_KEY=secret-value'
        (self.corpus / 'guide.md').write_text(self.private)
        self.db = self.root / 'traces.sqlite3'
        self.collection = MagicMock()
        self.collection.metadata = {}
        for target, value in [
            ('backend.tracing.TRACE_DB_PATH', self.db),
            ('backend.documents.CORPUS_DIR', self.corpus),
            ('backend.retrieval.DATASET_DIRECTORIES', {'baking': self.corpus, 'kestrel': self.corpus}),
            ('backend.rag_service.APP_SETTINGS', rag_service.Settings(800, 80)),
            ('backend.graph_index.KESTREL_DOCS', self.corpus),
            ('backend.graph_index.GRAPH_DIR', self.root / 'graph'),
            ('backend.graph_index.GRAPH_FILE', self.root / 'graph' / 'graph.json'),
        ]:
            self.enterContext(patch(target, value))
        self.enterContext(patch('backend.retrieval.load_settings', return_value={'chunk_size': 800, 'overlap': 80}))
        self.reset = self.enterContext(patch('backend.retrieval.reset_collection', return_value=self.collection))
        self.client = TestClient(app)

    def saved(self, trace_id):
        response = self.client.get('/api/traces/' + trace_id)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def trace_count(self):
        with sqlite3.connect(self.db) as connection:
            return connection.execute('SELECT COUNT(*) FROM traces').fetchone()[0]

    def test_manual_rebuild_records_counts_and_preserves_ids(self):
        stats = retrieval.rebuild_index(chunk_size=30, overlap=5)
        saved = self.saved(stats['trace_id'])
        self.assertEqual(saved['operation'], 'indexing')
        self.assertEqual(saved['status'], 'completed')
        self.assertEqual(saved['outcome'], 'indexed')
        self.assertEqual([s['name'] for s in saved['spans']], ['load_documents', 'chunking', 'embedding_indexing'])
        self.assertEqual(saved['spans'][0]['attributes'], {'dataset': 'baking', 'document_count': 1, 'preloaded': False})
        self.assertEqual(saved['spans'][1]['attributes'], {'chunk_size': 30, 'overlap': 5, 'chunk_count': stats['chunks']})
        self.assertEqual(saved['spans'][2]['attributes'], {'model': 'all-MiniLM-L6-v2', 'vector_count': stats['chunks']})
        self.assertTrue(all(s['status'] == 'completed' and s['duration_ms'] >= 0 for s in saved['spans']))
        self.assertEqual(self.collection.add.call_args.kwargs['ids'][0], retrieval.make_chunk_id('guide.md', 0))
        self.assertEqual(self.trace_count(), 1)

    def test_trace_never_contains_text_paths_or_exception_messages(self):
        self.collection.add.side_effect = RuntimeError(self.private)
        with self.assertRaises(RuntimeError):
            retrieval.rebuild_index()
        with sqlite3.connect(self.db) as connection:
            trace_id = connection.execute('SELECT trace_id FROM traces').fetchone()[0]
        saved = self.saved(trace_id)
        serialized = json.dumps(saved)
        for secret in (self.private, 'private.person', 'secret-value', 'guide.md', str(self.corpus)):
            self.assertNotIn(secret, serialized)
        self.assertEqual(saved['status'], 'failed')
        self.assertEqual(saved['spans'][-1]['error_type'], 'RuntimeError')
        self.assertEqual(saved['spans'][-1]['status'], 'failed')
        self.assertEqual(saved['spans'][-1]['attributes']['vector_count'], 0)
        self.collection.modify.assert_not_called()

    def test_load_failure_is_a_failed_span(self):
        with patch('backend.retrieval.load_documents', side_effect=OSError('private path')):
            with self.assertRaises(OSError):
                retrieval.rebuild_index()
        with sqlite3.connect(self.db) as connection:
            trace_id = connection.execute('SELECT trace_id FROM traces').fetchone()[0]
        saved = self.saved(trace_id)
        self.assertEqual(saved['status'], 'failed')
        self.assertEqual(saved['spans'][0]['name'], 'load_documents')
        self.assertEqual(saved['spans'][0]['status'], 'failed')
        self.reset.assert_not_called()

    def test_chunk_failure_is_a_failed_span(self):
        with patch('backend.retrieval.chunk_text', side_effect=ValueError('private contents')):
            with self.assertRaises(ValueError):
                retrieval.rebuild_index()
        with sqlite3.connect(self.db) as connection:
            trace_id = connection.execute('SELECT trace_id FROM traces').fetchone()[0]
        self.assertEqual(self.saved(trace_id)['spans'][-1]['name'], 'chunking')
        self.assertEqual(self.saved(trace_id)['spans'][-1]['status'], 'failed')
        self.reset.assert_not_called()

    def test_partial_batch_failure_counts_only_completed_batches(self):
        self.collection.add.side_effect = [None, RuntimeError('private')]
        with self.assertRaises(RuntimeError):
            retrieval.rebuild_index(chunk_size=1, overlap=0, documents=[{'source': 'guide.md', 'text': 'x' * 101}])
        with sqlite3.connect(self.db) as connection:
            trace_id = connection.execute('SELECT trace_id FROM traces').fetchone()[0]
        span = self.saved(trace_id)['spans'][-1]
        self.assertEqual(span['status'], 'failed')
        self.assertEqual(span['attributes']['vector_count'], 100)

    def test_supplied_trace_is_reused_and_not_finalized_by_rebuild(self):
        trace = tracing.create_trace('question')
        stats = retrieval.rebuild_index(trace=trace)
        self.assertEqual(stats['trace_id'], trace.trace_id)
        self.assertEqual(self.saved(trace.trace_id)['status'], 'running')
        self.assertEqual(self.trace_count(), 1)
        trace.finish('completed')

    def test_upload_uses_one_api_trace_and_exposes_it(self):
        response = self.client.post('/api/documents', files={'file': ('new.md', b'New source evidence', 'text/markdown')})
        self.assertEqual(response.status_code, 200, response.text)
        saved = self.saved(response.headers['X-Trace-ID'])
        self.assertEqual(saved['status'], 'completed')
        self.assertEqual(saved['spans'][0]['attributes']['document_count'], 2)
        self.assertEqual(self.trace_count(), 1)

    def test_failed_upload_retains_failed_trace_and_restores_files(self):
        self.collection.add.side_effect = RuntimeError('private')
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post('/api/documents', files={'file': ('new.md', b'Evidence', 'text/markdown')})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.saved(response.headers['X-Trace-ID'])['status'], 'failed')
        self.assertNotIn('private', response.text)
        self.assertFalse((self.corpus / 'new.md').exists())
        with sqlite3.connect(self.db) as connection:
            trace_id = connection.execute('SELECT trace_id FROM traces').fetchone()[0]
        self.assertEqual(self.saved(trace_id)['status'], 'failed')
        self.assertEqual(self.trace_count(), 1)

    def test_delete_and_rebuild_use_one_api_trace(self):
        response = self.client.delete('/api/documents/guide.md')
        self.assertEqual(response.status_code, 200, response.text)
        saved = self.saved(response.headers['X-Trace-ID'])
        self.assertEqual(saved['spans'][0]['attributes']['document_count'], 0)
        self.assertEqual(saved['spans'][-1]['attributes']['vector_count'], 0)
        self.assertEqual(self.trace_count(), 1)

    def test_delete_failure_restores_document_and_does_not_hide_error(self):
        self.collection.modify.side_effect = RuntimeError('private')
        with self.assertRaises(RuntimeError):
            documents.delete_document_and_reindex('guide.md')
        self.assertEqual((self.corpus / 'guide.md').read_text(), self.private)
        with sqlite3.connect(self.db) as connection:
            trace_id = connection.execute('SELECT trace_id FROM traces').fetchone()[0]
        self.assertEqual(self.saved(trace_id)['status'], 'failed')

    def test_settings_rebuild_reuses_one_trace(self):
        with patch('backend.retrieval.save_settings') as save:
            response = self.client.put('/api/settings', json={'chunk_size': 400, 'overlap': 40, 'top_k': 3, 'relevance_threshold': None})
        self.assertEqual(response.status_code, 200, response.text)
        save.assert_called_once_with(chunk_size=400, overlap=40)
        saved = self.saved(response.headers['X-Trace-ID'])
        self.assertEqual(saved['spans'][1]['attributes']['chunk_size'], 400)
        self.assertEqual(response.json()['index']['trace_id'], saved['trace_id'])
        self.assertEqual(self.trace_count(), 1)

    def test_failed_settings_save_marks_operation_failed(self):
        with patch('backend.retrieval.save_settings', side_effect=OSError('private')):
            with self.assertRaises(OSError):
                retrieval.update_index_settings(800, 80)
        with sqlite3.connect(self.db) as connection:
            trace_id = connection.execute('SELECT trace_id FROM traces').fetchone()[0]
        self.assertEqual(self.saved(trace_id)['status'], 'failed')

    def test_stale_rebuild_reuses_supplied_question_trace(self):
        trace = tracing.create_trace('question')
        with patch('backend.retrieval.get_collection', return_value=self.collection):
            retrieval.ensure_index_current('baking', 800, 80, trace=trace)
        self.assertEqual(len(self.saved(trace.trace_id)['spans']), 3)
        self.assertEqual(self.trace_count(), 1)
        trace.finish('completed')

    def test_current_index_does_not_create_indexing_trace(self):
        self.collection.metadata = retrieval._index_metadata(documents.load_documents(self.corpus), 800, 80)
        with patch('backend.retrieval.get_collection', return_value=self.collection), patch('backend.tracing.create_trace') as create:
            retrieval.ensure_index_current('baking', 800, 80)
        create.assert_not_called()
        self.reset.assert_not_called()

    def test_standalone_stale_rebuild_creates_one_trace(self):
        with patch('backend.retrieval.get_collection', return_value=self.collection):
            retrieval.ensure_index_current('kestrel', 800, 80)
        self.assertEqual(self.trace_count(), 1)

    def test_external_protocol_needs_only_span_and_trace_id(self):
        from tests.test_llm_tracing import FakeTrace
        trace = FakeTrace()
        stats = retrieval.rebuild_index(trace=trace)
        self.assertEqual(stats['trace_id'], trace.trace_id)
        self.assertEqual(len(trace.spans), 3)
        self.assertFalse(self.db.exists())

    def test_empty_corpus_is_successful_with_zero_vectors(self):
        (self.corpus / 'guide.md').unlink()
        stats = retrieval.rebuild_index()
        self.assertEqual(stats['chunks'], 0)
        self.assertEqual(self.saved(stats['trace_id'])['spans'][-1]['attributes']['vector_count'], 0)
        self.collection.add.assert_not_called()

    def test_invalid_settings_fail_before_reset(self):
        with self.assertRaises(ValueError):
            retrieval.rebuild_index(chunk_size=80, overlap=80)
        self.reset.assert_not_called()
        with sqlite3.connect(self.db) as connection:
            trace_id = connection.execute('SELECT trace_id FROM traces').fetchone()[0]
        self.assertEqual(self.saved(trace_id)['status'], 'failed')

    def test_ask_stale_rebuild_uses_question_trace_without_duplicate(self):
        self.collection.count.return_value = 0
        with patch('backend.retrieval.get_collection', return_value=self.collection):
            response = self.client.post('/api/ask', json={'question': 'What does the guide say?'})
        self.assertEqual(response.status_code, 200, response.text)
        saved = self.saved(response.headers['X-Trace-ID'])
        self.assertEqual(saved['operation'], 'question')
        self.assertEqual(saved['status'], 'completed')
        self.assertEqual([s['name'] for s in saved['spans']], ['load_documents', 'chunking', 'embedding_indexing', 'retrieval'])
        self.assertEqual(self.trace_count(), 1)

    def test_isolated_evaluation_index_uses_shared_trace(self):
        from evaluation import rag_evaluation
        trace = tracing.create_trace('indexing')
        client = MagicMock()
        client.create_collection.return_value = self.collection
        with patch.object(rag_evaluation, 'EVALUATION_DIR', self.root / 'evaluation'), patch.object(rag_evaluation.chromadb, 'PersistentClient', return_value=client), patch.object(rag_evaluation, 'SentenceTransformerEmbeddingFunction'):
            collection, count = rag_evaluation.build_isolated_index('baking', documents.load_documents(self.corpus), 800, 80, trace=trace)
        self.assertIs(collection, self.collection)
        self.assertEqual(count, 1)
        self.assertEqual(self.saved(trace.trace_id)['spans'][-1]['attributes']['vector_count'], 1)
        self.assertEqual(self.trace_count(), 1)
        trace.finish('completed')

    def test_isolated_evaluation_index_failure_is_traced(self):
        from evaluation import rag_evaluation
        with patch.object(rag_evaluation, 'EVALUATION_DIR', self.root / 'evaluation'), patch.object(rag_evaluation.chromadb, 'PersistentClient', side_effect=RuntimeError('private')):
            with self.assertRaises(RuntimeError):
                rag_evaluation.build_isolated_index('kestrel', documents.load_documents(self.corpus), 800, 80)
        with sqlite3.connect(self.db) as connection:
            trace_id = connection.execute('SELECT trace_id FROM traces').fetchone()[0]
        saved = self.saved(trace_id)
        self.assertEqual(saved['status'], 'failed')
        self.assertEqual(saved['spans'][-1]['name'], 'embedding_indexing')
        self.assertEqual(saved['spans'][-1]['status'], 'failed')

    def test_real_graph_extraction_logic_records_validated_triple_count(self):
        from types import SimpleNamespace
        from backend.graph_extraction import extract_graph_from_chunk
        content = {'triples': [{
            'subject': {'name': 'postroom', 'entity_type': 'SERVICE'},
            'relation': 'OWNED_BY',
            'object': {'name': 'Messaging', 'entity_type': 'TEAM'},
            'evidence_quote': 'postroom belongs to Messaging',
        }]}
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(content)))],
            usage=SimpleNamespace(prompt_tokens=20, completion_tokens=8),
        )
        client = MagicMock()
        client.chat.completions.create.return_value = response
        trace = tracing.create_trace('indexing')
        with patch('backend.graph_extraction.client', client):
            result = extract_graph_from_chunk({'id': 'safe-id', 'source': 'guide.md', 'text': 'postroom belongs to Messaging'}, trace=trace)
        self.assertEqual(len(result['triples']), 1)
        self.assertEqual(self.saved(trace.trace_id)['spans'][0]['attributes'], {'triple_count': 1, 'llm_calls': 1, 'input_tokens': 20, 'output_tokens': 8})
        trace.finish('completed')

    def graph_result(self):
        return {'triples': [], 'invalid_triples': [], 'llm_calls': 1, 'prompt_tokens': 12, 'completion_tokens': 3}

    def test_graph_build_records_actual_extraction_counts(self):
        with patch('backend.graph_extraction._extract_graph_from_chunk', return_value=self.graph_result()):
            result = graph_index.build_kestrel_graph()
        saved = self.saved(result['trace_id'])
        span = next(s for s in saved['spans'] if s['name'] == 'graph_extraction')
        self.assertEqual(span['attributes'], {'triple_count': 0, 'llm_calls': 1, 'input_tokens': 12, 'output_tokens': 3})
        self.assertEqual(saved['status'], 'completed')
        self.assertEqual(self.trace_count(), 1)
        self.assertNotIn('trace_id', json.loads((self.root / 'graph/graph.json').read_text()))

    def test_graph_partial_build_records_failure_without_claiming_success(self):
        (self.corpus / 'second.md').write_text('Second source')
        with patch('backend.graph_extraction._extract_graph_from_chunk', side_effect=[self.graph_result(), RuntimeError('private')]):
            result = graph_index.build_kestrel_graph()
        saved = self.saved(result['trace_id'])
        self.assertEqual(saved['status'], 'failed')
        self.assertEqual(saved['outcome'], 'partial')
        self.assertEqual([s['status'] for s in saved['spans'] if s['name'] == 'graph_extraction'], ['completed', 'failed'])
        self.assertNotIn('private', json.dumps(saved))

    def test_graph_retry_records_extraction_on_same_supplied_trace(self):
        with patch('backend.graph_extraction._extract_graph_from_chunk', side_effect=RuntimeError('private')):
            graph_index.build_kestrel_graph()
        trace = tracing.create_trace('indexing')
        with patch('backend.graph_extraction._extract_graph_from_chunk', return_value=self.graph_result()):
            result = graph_index.retry_failed_graph_chunks(delay_seconds=0, trace=trace)
        self.assertEqual(result['trace_id'], trace.trace_id)
        saved = self.saved(trace.trace_id)
        self.assertTrue(any(s['name'] == 'graph_extraction' for s in saved['spans']))
        self.assertEqual(saved['status'], 'running')
        trace.finish('completed')

    def test_graph_does_not_invent_missing_token_measurements(self):
        result = self.graph_result()
        result.update(prompt_tokens=None, completion_tokens=None)
        with patch('backend.graph_extraction._extract_graph_from_chunk', return_value=result):
            stats = graph_index.build_kestrel_graph()
        span = next(s for s in self.saved(stats['trace_id'])['spans'] if s['name'] == 'graph_extraction')
        self.assertEqual(span['attributes'], {'triple_count': 0, 'llm_calls': 1})


if __name__ == '__main__':
    unittest.main()
