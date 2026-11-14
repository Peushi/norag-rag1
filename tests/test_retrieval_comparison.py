import unittest

from fastapi.testclient import TestClient

from backend.main import app
from backend.retrieval_comparison import (
    RetrievalComparisonNotFoundError,
    get_retrieval_comparison,
)


class RetrievalComparisonTests(unittest.TestCase):
    def test_baking_comparison_contains_both_configurations(self):
        response = get_retrieval_comparison("retrieval-v2-baking")

        self.assertEqual(response.dataset, "baking")
        self.assertEqual(
            [(item.chunk_size, item.overlap) for item in response.configurations],
            [(800, 80), (400, 40)],
        )
        self.assertEqual(
            [len(item.questions) for item in response.configurations],
            [12, 12],
        )
        baseline = response.configurations[0]
        self.assertEqual(baseline.answerable_questions, 10)
        self.assertEqual(baseline.excluded_questions, 2)
        self.assertAlmostEqual(baseline.metrics["5"].hit_rate, 1.0)
        self.assertAlmostEqual(baseline.metrics["5"].recall, 0.7916666667)
        self.assertIn("split_answer", baseline.question_type_breakdown)

    def test_kestrel_comparison_preserves_unanswerable_null_metrics_and_ranks(self):
        response = get_retrieval_comparison("retrieval-v2-kestrel")

        self.assertEqual(response.dataset, "kestrel")
        for configuration in response.configurations:
            self.assertEqual(len(configuration.questions), 10)
            unanswerable = next(
                question
                for question in configuration.questions
                if not question.answerable
            )
            self.assertIsNone(unanswerable.retrieval_metrics)

        baseline_q01 = next(
            question
            for question in response.configurations[0].questions
            if question.id == "q01"
        )
        self.assertEqual(
            baseline_q01.evidence[0].matched_chunks[0].rank,
            7,
        )
        self.assertEqual(baseline_q01.evaluation_chunks[0].rank, 1)

    def test_unknown_experiment_is_not_found(self):
        with self.assertRaises(RetrievalComparisonNotFoundError):
            get_retrieval_comparison("unknown-experiment")

    def test_api_exposes_both_comparisons_and_rejects_unknown_experiment(self):
        client = TestClient(app)
        for dataset in ("baking", "kestrel"):
            experiment_id = f"retrieval-v2-{dataset}"
            response = client.get(
                f"/api/evaluations/retrieval/{experiment_id}/results"
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["dataset"], dataset)

        missing = client.get(
            "/api/evaluations/retrieval/unknown-experiment/results"
        )
        self.assertEqual(missing.status_code, 404)


if __name__ == "__main__":
    unittest.main()
