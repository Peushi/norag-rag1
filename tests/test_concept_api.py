"""HTTP routes for the Concept Map explorer and the document reader.

Reuses the small fake graph from the Concept Map service tests, with a
temporary trace database, so the real graph and traces are never touched.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import rag_service
from backend.main import app

# Import the module, not the class, so unittest does not collect its tests twice.
from tests import test_concept_map as concept_setup


class ConceptApiTests(unittest.TestCase):
    setUp_graph = concept_setup.ConceptMapTests.setUp
    write_graph = concept_setup.ConceptMapTests.write_graph
    identifier = concept_setup.ConceptMapTests.identifier

    def setUp(self):
        self.setUp_graph()
        trace_dir = tempfile.TemporaryDirectory()
        self.addCleanup(trace_dir.cleanup)
        self.enterContext(
            patch("backend.tracing.TRACE_DB_PATH", Path(trace_dir.name) / "traces.sqlite3")
        )
        self.client = TestClient(app)

    def test_search_returns_matching_concepts(self):
        response = self.client.get("/api/concepts", params={"query": "post"})

        self.assertEqual(response.status_code, 200, response.text)
        concepts = response.json()["concepts"]
        self.assertEqual([c["name"] for c in concepts], ["postroom"])
        self.assertEqual(set(concepts[0]), {"id", "name", "type"})

    def test_opening_a_concept_returns_relations_and_a_trace(self):
        concept_id = self.identifier("postroom", "SERVICE")

        response = self.client.get(f"/api/concepts/{concept_id}")

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["concept"]["name"], "postroom")
        relations = {(n["relation"], n["direction"], n["concept"]["name"]) for n in body["neighbours"]}
        self.assertIn(("OWNED_BY", "outgoing", "Messaging"), relations)
        self.assertIn(("REPLACES", "outgoing", "mailman"), relations)
        self.assertTrue(all(n["chunk_ids"] for n in body["neighbours"]))

        self.assertEqual(response.headers["x-trace-id"], body["trace_id"])
        trace = self.client.get(f"/api/traces/{body['trace_id']}").json()
        self.assertEqual(trace["operation"], "concept_map")
        self.assertEqual(trace["outcome"], "found")
        self.assertEqual([s["name"] for s in trace["spans"]], ["concept_neighbourhood"])
        self.assertNotIn("postroom", str(trace))

    def test_unknown_concept_is_404_with_a_failed_trace(self):
        response = self.client.get("/api/concepts/concept_" + "0" * 64)

        self.assertEqual(response.status_code, 404)
        trace = self.client.get(f"/api/traces/{response.headers['x-trace-id']}").json()
        self.assertEqual(trace["status"], "failed")
        self.assertEqual(trace["outcome"], "not_found")

    def test_mismatched_chunk_settings_explain_why_the_map_is_unavailable(self):
        with patch.object(rag_service, "APP_SETTINGS", rag_service.Settings(400, 40)):
            listing = self.client.get("/api/concepts")
            opening = self.client.get(
                f"/api/concepts/{self.identifier('postroom', 'SERVICE')}"
            )

        for response in (listing, opening):
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["error"]["code"], "GRAPH_UNAVAILABLE")
            self.assertIn("chunk_size=800", response.json()["error"]["message"])
        trace = self.client.get(f"/api/traces/{opening.headers['x-trace-id']}").json()
        self.assertEqual(trace["outcome"], "unavailable")


class DocumentTextApiTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.baking = root / "baking"
        self.kestrel = root / "kestrel"
        self.baking.mkdir()
        self.kestrel.mkdir()
        (self.baking / "same.md").write_text("Baking original", encoding="utf-8")
        (self.kestrel / "same.md").write_text("Kestrel original", encoding="utf-8")
        self.enterContext(
            patch(
                "backend.rag_service.DATASET_DIRECTORIES",
                {"baking": self.baking, "kestrel": self.kestrel},
            )
        )
        self.client = TestClient(app)

    def test_reads_the_document_from_the_selected_dataset(self):
        response = self.client.get(
            "/api/document-text", params={"document_id": "same.md", "dataset": "kestrel"}
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json(),
            {"document_id": "same.md", "dataset": "kestrel", "text": "Kestrel original"},
        )

    def test_missing_and_unsafe_paths_are_refused(self):
        missing = self.client.get(
            "/api/document-text", params={"document_id": "nope.md", "dataset": "kestrel"}
        )
        traversal = self.client.get(
            "/api/document-text",
            params={"document_id": "../../backend/main.py", "dataset": "baking"},
        )

        self.assertEqual(missing.status_code, 404)
        self.assertEqual(traversal.status_code, 422)
        self.assertNotIn("import", traversal.text)


if __name__ == "__main__":
    unittest.main()
