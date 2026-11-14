import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.schemas import AskResponse
from backend.tracing import create_trace


class TraceRecorderTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.trace_db_patch = patch(
            "backend.tracing.TRACE_DB_PATH",
            Path(self.temp_dir.name) / "traces.sqlite3",
        )
        self.trace_db_patch.start()

    def tearDown(self):
        self.trace_db_patch.stop()
        self.temp_dir.cleanup()

    def test_records_successful_span_and_trace(self):
        trace = create_trace("question")
        with trace.span(
            "llm_generation",
            attributes={"model": "test-model"},
        ) as span:
            span.set_attribute("input_tokens", 12)
        trace.set_outcome("answered")
        trace.finish("completed")

        with TestClient(app) as client:
            response = client.get(f"/api/traces/{trace.trace_id}")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["operation"], "question")
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["outcome"], "answered")
        self.assertEqual(data["spans"][0]["name"], "llm_generation")
        self.assertEqual(data["spans"][0]["status"], "completed")
        self.assertEqual(data["spans"][0]["attributes"]["input_tokens"], 12)
        self.assertGreaterEqual(data["spans"][0]["duration_ms"], 0)

    def test_failed_span_stores_error_type_without_message(self):
        trace = create_trace("question")
        try:
            with trace.span("retrieval"):
                raise ValueError("private query text")
        except ValueError:
            pass
        trace.finish("failed")

        from backend.tracing import get_trace

        saved = get_trace(trace.trace_id)
        self.assertEqual(saved["status"], "failed")
        self.assertEqual(saved["spans"][0]["status"], "failed")
        self.assertEqual(saved["spans"][0]["error_type"], "ValueError")
        self.assertNotIn("private query text", str(saved))

    def test_rejects_sensitive_attribute_names(self):
        trace = create_trace("question")
        with self.assertRaisesRegex(ValueError, "not permitted"):
            trace.span("unsafe", attributes={"prompt_text": "private"})


class RetrievalSpanTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.trace_db_patch = patch(
            "backend.tracing.TRACE_DB_PATH",
            Path(self.temp_dir.name) / "traces.sqlite3",
        )
        self.trace_db_patch.start()

    def tearDown(self):
        self.trace_db_patch.stop()
        self.temp_dir.cleanup()

    def _retrieval(self):
        from backend.retrieval_orchestrator import OrchestratedRetrieval

        return OrchestratedRetrieval(
            chunks=[
                {
                    "id": "abc123::chunk_0002",
                    "text": "SECRET CHUNK TEXT about the descaling mode",
                    "source": "manual.txt",
                    "position": 2,
                    "final_rank": 1,
                    "final_score": 0.0325,
                    "retrievers": [
                        {"retriever": "dense", "rank": 2, "score": 0.31, "score_type": "cosine_distance"},
                        {"retriever": "bm25", "rank": 1, "score": 7.2, "score_type": "bm25"},
                    ],
                },
                {
                    "id": "abc123::chunk_0005",
                    "text": "Another private passage",
                    "source": "manual.txt",
                    "position": 5,
                    "final_rank": 2,
                    "final_score": 0.0161,
                    "retrievers": [{"retriever": "bm25", "rank": 3}],
                },
            ],
            graph_paths=[],
            retrievers=("dense", "bm25"),
        )

    def test_retrieval_span_records_ranked_chunk_ids_without_text(self):
        from backend.rag_service import ask_question
        from backend.tracing import get_trace

        trace = create_trace("question")
        answer = AskResponse(status="not_found", answer="Not found.")
        with patch(
            "backend.rag_service.retrieve_selected_chunks",
            return_value=self._retrieval(),
        ), patch("backend.rag_service.generate_answer", return_value=answer):
            ask_question(
                "How do I descale?",
                retrievers=["dense", "bm25"],
                document_ids=["manual.txt"],
                top_k=2,
                trace=trace,
            )
        trace.finish("completed")

        span = get_trace(trace.trace_id)["spans"][0]
        attributes = span["attributes"]
        self.assertEqual(span["name"], "retrieval")
        self.assertEqual(attributes["retrievers"], "dense,bm25")
        self.assertEqual(attributes["top_k"], 2)
        self.assertEqual(attributes["document_filter"], "selected")
        self.assertEqual(attributes["selected_document_count"], 1)
        self.assertEqual(attributes["result_count"], 2)
        self.assertEqual(attributes["result.1.chunk_id"], "abc123::chunk_0002")
        self.assertEqual(attributes["result.1.position"], 2)
        self.assertEqual(
            attributes["result.1.found_by"],
            "dense#2 (cosine_distance 0.3100); bm25#1 (bm25 7.2000)",
        )
        self.assertEqual(attributes["result.2.found_by"], "bm25#3")
        saved = str(get_trace(trace.trace_id))
        self.assertNotIn("SECRET CHUNK TEXT", saved)
        self.assertNotIn("private passage", saved)
        self.assertNotIn("How do I descale", saved)

    def test_long_found_by_summary_is_truncated(self):
        from backend.rag_service import TRACE_STRING_LIMIT, _found_by

        contributions = [
            {"retriever": "dense", "rank": rank, "score": 0.123456, "score_type": "cosine_distance"}
            for rank in range(1, 20)
        ]
        self.assertLessEqual(len(_found_by(contributions)), TRACE_STRING_LIMIT)


class AskTraceApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.trace_db_patch = patch(
            "backend.tracing.TRACE_DB_PATH",
            Path(self.temp_dir.name) / "traces.sqlite3",
        )
        self.trace_db_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.trace_db_patch.stop()
        self.temp_dir.cleanup()

    def test_ask_passes_trace_and_returns_trace_id(self):
        answer = AskResponse(
            status="not_found",
            answer="No supporting evidence.",
        )

        def fake_ask(**kwargs):
            with kwargs["trace"].span("retrieval"):
                pass
            return answer

        with patch("backend.main.ask_question", side_effect=fake_ask) as ask:
            response = self.client.post(
                "/api/ask",
                json={"question": "What happened?"},
            )

        self.assertEqual(response.status_code, 200, response.text)
        trace_id = response.json()["trace_id"]
        self.assertEqual(response.headers["x-trace-id"], trace_id)
        self.assertIsNotNone(ask.call_args.kwargs["trace"])
        trace_response = self.client.get(f"/api/traces/{trace_id}")
        self.assertEqual(trace_response.status_code, 200)
        self.assertEqual(trace_response.json()["outcome"], "not_found")
        self.assertEqual(
            [span["name"] for span in trace_response.json()["spans"]],
            ["retrieval"],
        )

    def test_invalid_ask_still_has_a_failed_trace(self):
        response = self.client.post(
            "/api/ask",
            json={"question": "What happened?", "retrievers": []},
        )

        self.assertEqual(response.status_code, 422)
        trace_id = response.headers["x-trace-id"]
        trace_response = self.client.get(f"/api/traces/{trace_id}")
        self.assertEqual(trace_response.status_code, 200)
        self.assertEqual(trace_response.json()["status"], "failed")

    def test_missing_trace_returns_404(self):
        response = self.client.get("/api/traces/not-a-real-trace")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
