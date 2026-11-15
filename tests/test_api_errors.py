"""Error responses a user can act on: upload limits, duplicates, and crashes.

Reuses the temporary corpus and trace database from the indexing trace tests,
so the real corpus, index, and traces are never touched.
"""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import MAX_UPLOAD_BYTES, app

# Import the module, not the class, so unittest does not collect its tests twice.
from tests import test_indexing_tracing as indexing_setup


class ApiErrorTests(unittest.TestCase):
    setUp_corpus = indexing_setup.IndexingTraceTests.setUp
    saved = indexing_setup.IndexingTraceTests.saved

    def setUp(self):
        self.setUp_corpus()
        # Crashes must come back as responses, not be re-raised into the test.
        self.client = TestClient(app, raise_server_exceptions=False)

    def upload(self, name, content):
        return self.client.post('/api/documents', files={'file': (name, content, 'text/markdown')})

    def error(self, response):
        return response.json()['error']

    def test_duplicate_upload_names_the_file_and_what_to_do(self):
        response = self.upload('guide.md', b'Another guide')

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            self.error(response)['message'],
            '“guide.md” is already in your library. Remove it first, or rename the file.',
        )

    def test_empty_and_oversized_uploads_are_refused_before_indexing(self):
        empty = self.upload('empty.md', b'  \n')
        too_large = self.upload('big.md', b'a' * (MAX_UPLOAD_BYTES + 1))

        self.assertEqual(empty.status_code, 422)
        self.assertEqual(self.error(empty)['message'], 'This file is empty.')
        self.assertEqual(too_large.status_code, 413)
        self.assertIn('up to 1 MB', self.error(too_large)['message'])
        self.reset.assert_not_called()

    def test_non_utf8_upload_explains_how_to_fix_it(self):
        response = self.upload('latin.md', 'crème brûlée'.encode('latin-1'))

        self.assertEqual(response.status_code, 422)
        self.assertIn('UTF-8', self.error(response)['message'])

    def test_a_crashed_question_returns_json_with_its_trace(self):
        with patch('backend.main.ask_question', side_effect=RuntimeError('/secret/path')):
            response = self.client.post('/api/ask', json={'question': 'How long do I proof dough?'})

        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.error(response)['code'], 'INTERNAL_ERROR')
        self.assertTrue(self.error(response)['retryable'])
        self.assertNotIn('secret', response.text)
        trace = self.saved(response.headers['X-Trace-ID'])
        self.assertEqual(trace['operation'], 'question')
        self.assertEqual(trace['status'], 'failed')

    def test_a_crash_elsewhere_returns_json_without_details(self):
        with patch('backend.main.list_documents', side_effect=RuntimeError('/secret/path')):
            response = self.client.get('/api/documents')

        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.error(response)['code'], 'INTERNAL_ERROR')
        self.assertNotIn('secret', response.text)

    def test_validation_errors_use_the_shared_error_shape(self):
        response = self.client.post('/api/ask', json={})

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            self.error(response),
            {'code': 'VALIDATION_ERROR', 'message': 'Request validation failed.', 'retryable': False},
        )


if __name__ == '__main__':
    unittest.main()
