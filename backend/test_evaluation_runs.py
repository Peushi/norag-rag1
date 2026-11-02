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

        def fake_evaluate(*, dataset, top_k, chunk_size, overlap, max_distance, output_path, limit):
            self.assertEqual(dataset, "baking")
            self.assertEqual(top_k, 5)
            self.assertEqual(chunk_size, 800)
            self.assertEqual(overlap, 80)
            self.assertIsNone(max_distance)
            self.assertEqual(limit, 1)
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


if __name__ == "__main__":
    unittest.main()
