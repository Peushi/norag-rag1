
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import graph_index


class GraphIndexCostTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        self.docs_dir = self.root / "docs"
        self.docs_dir.mkdir()
        (self.docs_dir / "guide.md").write_text(
            "Test document content",
            encoding="utf-8",
        )

        self.graph_dir = self.root / "graph"
        self.graph_file = self.graph_dir / "graph.json"

        self.chunks = [
            {"text": "First chunk", "position": 0},
            {"text": "Second chunk", "position": 1},
        ]

        self.path_patches = [
            patch.object(graph_index, "KESTREL_DOCS", self.docs_dir),
            patch.object(graph_index, "GRAPH_DIR", self.graph_dir),
            patch.object(graph_index, "GRAPH_FILE", self.graph_file),
            patch.object(
                graph_index,
                "chunk_text",
                return_value=self.chunks,
            ),
            patch.object(
                graph_index,
                "make_chunk_id",
                side_effect=lambda source, position: f"{source}:{position}",
            ),
        ]

        for path_patch in self.path_patches:
            path_patch.start()
            self.addCleanup(path_patch.stop)

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def extraction_result(cost):
        return {
            "triples": [],
            "invalid_triples": [],
            "llm_calls": 1,
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "cost_usd": cost,
        }

    def write_existing_graph(self, cost=0.001):
        self.graph_dir.mkdir(parents=True, exist_ok=True)

        graph_data = {
            "triples": [],
            "invalid_triples": [],
            "statistics": {
                "successful_calls": 2,
                "failed_chunks": 1,
                "triples": 0,
                "prompt_tokens": 100,
                "completion_tokens": 200,
                "total_tokens": 300,
                "cost_usd": cost,
                "build_time_seconds": 1.0,
            },
            "failed_chunks": [
                {
                    "chunk_id": "guide.md:0",
                    "source": "guide.md",
                    "position": 0,
                    "error": "Temporary extraction failure",
                }
            ],
        }

        self.graph_file.write_text(
            json.dumps(graph_data),
            encoding="utf-8",
        )

    def test_build_sums_extraction_costs(self):
        with patch.object(
            graph_index,
            "extract_graph_from_chunk",
            side_effect=[
                self.extraction_result(0.001),
                self.extraction_result(0.002),
            ],
        ):
            result = graph_index.build_kestrel_graph()

        self.assertEqual(result["statistics"]["cost_usd"], 0.003)

    def test_build_cost_is_none_when_usage_is_missing(self):
        with patch.object(
            graph_index,
            "extract_graph_from_chunk",
            side_effect=[
                self.extraction_result(0.001),
                self.extraction_result(None),
            ],
        ):
            result = graph_index.build_kestrel_graph()

        self.assertIsNone(result["statistics"]["cost_usd"])

    def test_retry_adds_retry_cost_to_original_cost(self):
        self.write_existing_graph(cost=0.001)

        with (
            patch.object(
                graph_index,
                "extract_graph_from_chunk",
                return_value=self.extraction_result(0.002),
            ),
            patch.object(graph_index.time, "sleep"),
        ):
            result = graph_index.retry_failed_graph_chunks(
                delay_seconds=0,
            )

        statistics = result["statistics"]

        self.assertEqual(statistics["retry_cost_usd"], 0.002)
        self.assertEqual(statistics["cost_usd"], 0.003)
        self.assertEqual(statistics["failed_chunks"], 0)

    def test_retry_total_cost_is_none_when_retry_usage_is_missing(self):
        self.write_existing_graph(cost=0.001)

        with (
            patch.object(
                graph_index,
                "extract_graph_from_chunk",
                return_value=self.extraction_result(None),
            ),
            patch.object(graph_index.time, "sleep"),
        ):
            result = graph_index.retry_failed_graph_chunks(
                delay_seconds=0,
            )

        statistics = result["statistics"]

        self.assertIsNone(statistics["retry_cost_usd"])
        self.assertIsNone(statistics["cost_usd"])


if __name__ == "__main__":
    unittest.main()
