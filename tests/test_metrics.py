"""The metrics page's numbers, computed from traces with known answers."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.metrics import classify_question, compute_metrics, percentile
from backend.tracing import create_trace


def span(name, ms, error=None, **attributes):
    entry = {"name": name, "status": "failed" if error else "completed", "duration_ms": ms, "attributes": attributes}
    if error:
        entry["error_type"] = error
    return entry


def question(outcome, status="completed", day="2026-11-15", seconds=2.0, spans=()):
    return {
        "operation": "question", "status": status, "outcome": outcome,
        "started_at": f"{day}T10:00:00+00:00",
        "completed_at": None if status == "running" else f"{day}T10:00:{seconds:06.3f}+00:00",
        "spans": list(spans),
    }


ANSWERED = question("answered", seconds=2.0, spans=[
    span("retrieval", 20), span("pii_redaction", 5),
    span("llm_generation", 1500, input_tokens=1000, output_tokens=200, cost_usd=0.001),
    span("response_validation", 1), span("citation_verification", 1),
])
ABSTAINED = question("not_found", seconds=1.0, day="2026-11-16", spans=[
    span("retrieval", 30), span("llm_generation", 800, input_tokens=900, output_tokens=40, cost_usd=0.0005),
])
INVALID = question(None, status="failed", seconds=3.0, spans=[
    span("retrieval", 10), span("llm_generation", 1200, input_tokens=950, output_tokens=150, cost_usd=0.0007),
    span("response_validation", 1, error="LLMResponseError"),
])
ERROR = question(None, status="failed", seconds=0.5, spans=[span("retrieval", 4, error="RetrieverUnavailableError")])
RUNNING = question(None, status="running")
GRAPH_BUILD = {
    "operation": "indexing", "status": "completed", "outcome": "indexed",
    "started_at": "2026-11-16T09:00:00+00:00", "completed_at": "2026-11-16T09:00:10+00:00",
    "spans": [
        span("graph_plan", 5, new_count=2, changed_count=1, removed_count=0, chunks_to_extract=3),
        span("graph_extraction", 900, input_tokens=600, output_tokens=100, cost_usd=0.0004),
        span("graph_extraction", 950, input_tokens=600, output_tokens=100, cost_usd=0.0004),
        span("graph_extraction", 1000, input_tokens=600, output_tokens=100, cost_usd=0.0004),
        span("graph_save", 3, documents_left_count=0),
    ],
}
UPLOAD = {
    "operation": "indexing", "status": "completed", "outcome": "indexed",
    "started_at": "2026-11-15T08:00:00+00:00", "completed_at": "2026-11-15T08:00:02+00:00",
    "spans": [span("document_storage", 2), span("embedding_indexing", 1500)],
}


class MetricsTests(unittest.TestCase):
    def setUp(self):
        self.metrics = compute_metrics([ANSWERED, ABSTAINED, INVALID, ERROR, RUNNING, GRAPH_BUILD, UPLOAD], 30)

    def test_outcomes_follow_the_trace_and_its_failed_step(self):
        self.assertEqual(
            [classify_question(t) for t in (ANSWERED, ABSTAINED, INVALID, ERROR, RUNNING)],
            ["answered", "abstained", "invalid", "error", "in_progress"],
        )
        self.assertEqual(self.metrics["questions"]["total"], 5)
        self.assertEqual(
            self.metrics["questions"]["outcomes"],
            {"answered": 1, "abstained": 1, "invalid": 1, "error": 1, "in_progress": 1},
        )

    def test_percentiles_use_the_nearest_rank(self):
        values = list(range(1, 21))  # 1..20
        self.assertEqual(percentile(values, 50), 10)
        self.assertEqual(percentile(values, 95), 19)
        self.assertEqual(percentile([7], 95), 7)
        self.assertIsNone(percentile([], 50))

    def test_latency_covers_the_whole_request_and_each_step_in_pipeline_order(self):
        latency = self.metrics["latency"]
        # Finished questions only: 2.0, 1.0, 3.0, 0.5 s.
        self.assertEqual(latency["request"], {"count": 4, "p50_ms": 1000.0, "p95_ms": 3000.0})
        steps = [s["step"] for s in latency["steps"]]
        self.assertEqual(steps[:4], ["retrieval", "pii_redaction", "llm_generation", "response_validation"])
        generation = next(s for s in latency["steps"] if s["step"] == "llm_generation")
        self.assertEqual((generation["count"], generation["p50_ms"], generation["p95_ms"]), (3, 1200, 1500))

    def test_tokens_and_cost_per_question_count_every_llm_call(self):
        per_question = self.metrics["per_question"]
        self.assertEqual(per_question["questions_with_llm_call"], 3)
        self.assertEqual(per_question["total_input_tokens"], 2850)
        self.assertEqual(per_question["total_cost_usd"], 0.0022)
        self.assertEqual(per_question["mean_cost_usd"], round(0.0022 / 3, 6))
        self.assertEqual(per_question["p95_cost_usd"], 0.001)

    def test_cost_per_indexed_document_comes_from_concept_map_builds(self):
        per_document = self.metrics["per_document"]
        self.assertEqual(per_document["uploads"], 1)
        self.assertEqual(per_document["upload_cost_usd"], 0.0)
        self.assertEqual(per_document["graph_documents_read"], 3)
        self.assertEqual(per_document["graph_llm_calls"], 3)
        self.assertEqual(per_document["graph_failed_calls"], 0)
        self.assertEqual(per_document["graph_cost_usd"], 0.0012)
        self.assertEqual(per_document["graph_cost_per_document_usd"], 0.0004)

    def test_a_failed_then_retried_document_is_counted_once(self):
        failed_build = {
            **GRAPH_BUILD,
            "spans": [
                span("graph_plan", 5, new_count=1, changed_count=0),
                span("graph_extraction", 300, error="InternalServerError"),
                span("graph_save", 3, documents_left_count=0, failed_document_count=1),
            ],
        }
        retry = {
            **GRAPH_BUILD,
            "spans": [
                span("graph_plan", 5, new_count=0, changed_count=1),
                span("graph_extraction", 900, input_tokens=600, output_tokens=100, cost_usd=0.0007),
                span("graph_save", 3, documents_left_count=0, failed_document_count=0),
            ],
        }
        per_document = compute_metrics([failed_build, retry], 30)["per_document"]
        self.assertEqual(per_document["graph_documents_read"], 1)
        self.assertEqual(per_document["graph_failed_calls"], 1)
        self.assertEqual(per_document["graph_cost_per_document_usd"], 0.0007)

    def test_per_day_groups_by_utc_date_newest_first(self):
        days = {d["date"]: d for d in self.metrics["per_day"]}
        self.assertEqual([d["date"] for d in self.metrics["per_day"]], ["2026-11-16", "2026-11-15"])
        self.assertEqual(days["2026-11-15"]["questions"], 4)
        self.assertEqual(days["2026-11-15"]["question_cost_usd"], 0.0017)
        self.assertEqual(days["2026-11-16"]["indexing_cost_usd"], 0.0012)
        self.assertEqual(days["2026-11-16"]["total_cost_usd"], 0.0017)

    def test_empty_traces_give_an_empty_page_not_an_error(self):
        empty = compute_metrics([], 7)
        self.assertEqual(empty["questions"]["total"], 0)
        self.assertIsNone(empty["latency"]["request"]["p50_ms"])
        self.assertIsNone(empty["per_question"]["mean_cost_usd"])
        self.assertEqual(empty["per_day"], [])


class MetricsApiTests(unittest.TestCase):
    def test_the_endpoint_reads_the_stored_traces(self):
        with tempfile.TemporaryDirectory() as folder, patch(
            "backend.tracing.TRACE_DB_PATH", Path(folder) / "traces.sqlite3"
        ):
            trace = create_trace("question")
            with trace.span("llm_generation", attributes={"input_tokens": 10, "output_tokens": 5, "cost_usd": 0.0001}):
                pass
            trace.set_outcome("answered")
            trace.finish("completed")

            response = TestClient(app).get("/api/metrics", params={"days": 7})

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["window_days"], 7)
        self.assertEqual(body["questions"]["outcomes"]["answered"], 1)
        self.assertEqual(body["per_question"]["total_input_tokens"], 10)

    def test_the_window_is_limited_to_the_trace_retention(self):
        self.assertEqual(TestClient(app).get("/api/metrics", params={"days": 90}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
