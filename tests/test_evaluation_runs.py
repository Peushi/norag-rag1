import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import backend.evaluation_runs as evaluation_runs
from backend.schemas import EvaluationRunRequest


class EvaluationRunTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_runs_dir = evaluation_runs.RUNS_DIR
        evaluation_runs.RUNS_DIR = Path(self.temporary_directory.name)
        with evaluation_runs._lock:
            evaluation_runs._active_datasets.clear()

    def tearDown(self):
        evaluation_runs.RUNS_DIR = self.original_runs_dir
        with evaluation_runs._lock:
            evaluation_runs._active_datasets.clear()
        self.temporary_directory.cleanup()

    def test_run_executes_and_persists_results(self):
        request = EvaluationRunRequest(
            dataset="baking",
            top_k=5,
            chunk_size=800,
            overlap=80,
            limit=1,
        )
        run = evaluation_runs.create_run(request)

        fake_runner = types.ModuleType("evaluation.rag_evaluation")

        def fake_evaluate(
            *,
            dataset,
            top_k,
            chunk_size,
            overlap,
            max_distance,
            output_path,
            limit,
            retrievers,
            compare_path_context,
            generate_answers,
        ):
            self.assertEqual(dataset, "baking")
            self.assertEqual(top_k, 5)
            self.assertEqual(chunk_size, 800)
            self.assertEqual(overlap, 80)
            self.assertIsNone(max_distance)
            self.assertEqual(limit, 1)
            self.assertEqual(retrievers, ["dense"])
            self.assertFalse(compare_path_context)
            self.assertFalse(generate_answers)
            Path(output_path).write_text(
                json.dumps({"id": "B01", "question": "test?"}) + "\n",
                encoding="utf-8",
            )

        fake_runner.run_evaluation = fake_evaluate

        with patch.dict("sys.modules", {"evaluation.rag_evaluation": fake_runner}):
            evaluation_runs.execute_run(run.run_id, request)

        completed = evaluation_runs.get_run(run.run_id)
        self.assertEqual(completed.status, "completed")
        self.assertEqual(
            evaluation_runs.get_run_results(run.run_id),
            [{"id": "B01", "question": "test?"}],
        )

    def test_only_one_run_per_dataset_can_be_active(self):
        request = EvaluationRunRequest(dataset="kestrel")
        evaluation_runs.create_run(request)

        with self.assertRaises(evaluation_runs.EvaluationAlreadyRunningError):
            evaluation_runs.create_run(request)

    def test_persists_retrieval_configuration(self):
        request = EvaluationRunRequest(
            dataset="kestrel",
            retrievers=["dense", "graph"],
            compare_path_context=True,
            generate_answers=True,
        )
        run = evaluation_runs.create_run(request)

        self.assertEqual(run.retrievers, ["dense", "graph"])
        self.assertTrue(run.compare_path_context)
        self.assertTrue(run.generate_answers)

    def test_path_context_comparison_requires_graph_and_generation(self):
        with self.assertRaisesRegex(ValueError, "requires graph retrieval"):
            EvaluationRunRequest(
                dataset="kestrel",
                retrievers=["dense"],
                compare_path_context=True,
                generate_answers=True,
            )

        with self.assertRaisesRegex(ValueError, "requires answer generation"):
            EvaluationRunRequest(
                dataset="kestrel",
                retrievers=["graph"],
                compare_path_context=True,
            )

    def test_required_retriever_configurations_are_validated(self):
        configurations = [
            ["dense"],
            ["bm25"],
            ["dense", "bm25"],
            ["graph"],
            ["dense", "graph"],
            ["dense", "bm25", "graph"],
        ]
        for retrievers in configurations:
            with self.subTest(retrievers=retrievers):
                request = EvaluationRunRequest(
                    dataset="kestrel" if "graph" in retrievers else "baking",
                    retrievers=retrievers,
                )
                self.assertEqual(request.retrievers, retrievers)

        with self.assertRaisesRegex(ValueError, "only available for the kestrel"):
            EvaluationRunRequest(dataset="baking", retrievers=["graph"])


if __name__ == "__main__":
    unittest.main()
