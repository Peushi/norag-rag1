import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from evaluation import rag_evaluation as runner


class EvaluationModeTests(unittest.TestCase):
    def test_hybrid_uses_real_rrf_with_typed_bm25_contributions(self):
        from backend.bm25 import BM25Index
        documents = [{"source": "guide.md", "text": "A rare fact."}]
        chunk = BM25Index(documents).chunks[0]
        question = {"id": "test", "question": "rare", "type": "other", "answerable": True,
                    "evidence": [{"source": "guide.md", "quote": "A rare fact."}]}
        with tempfile.TemporaryDirectory() as temp, contextlib.ExitStack() as stack:
            output = Path(temp) / "hybrid.jsonl"
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            stack.enter_context(patch.object(runner, "load_questions", return_value=[question]))
            stack.enter_context(patch.object(runner, "load_documents", return_value=documents))
            stack.enter_context(patch.object(runner, "build_isolated_index", return_value=(object(), 1)))
            stack.enter_context(patch.object(runner, "retrieve", return_value=[{**chunk, "distance": 0.2}]))
            generate = stack.enter_context(patch.object(runner, "generate_answer"))
            runner.run_evaluation(dataset="baking", retrievers=["dense", "bm25"], output_path=output)
            row = json.loads(output.read_text())
            self.assertAlmostEqual(row["fused_chunks"][0]["final_score"], 2 / 61)
            self.assertEqual([c["retriever"] for c in row["fused_chunks"][0]["retrievers"]], ["bm25", "dense"])
            self.assertEqual(row["retrieval_metrics"]["1"]["recall"], 1)
            generate.assert_not_called()

    def test_bm25_only_skips_dense_index_and_generation(self):
        question = {"id": "test", "question": "bread", "type": "other", "answerable": True,
                    "evidence": [{"source": "guide.md", "quote": "bread"}]}
        with tempfile.TemporaryDirectory() as temp, contextlib.ExitStack() as stack:
            output = Path(temp) / "bm25.jsonl"
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            stack.enter_context(patch.object(runner, "load_questions", return_value=[question]))
            stack.enter_context(patch.object(runner, "load_documents", return_value=[{"source": "guide.md", "text": "bread"}]))
            build = stack.enter_context(patch.object(runner, "build_isolated_index"))
            generate = stack.enter_context(patch.object(runner, "generate_answer"))
            runner.run_evaluation(dataset="baking", retrievers=["bm25"], output_path=output)
            row = json.loads(output.read_text())
            self.assertIsNone(row["evaluation_chunks"][0]["distance"])
            self.assertEqual(row["retrieval_metrics"]["1"]["recall"], 1)
            build.assert_not_called()
            generate.assert_not_called()

    def test_unregistered_retrievers_fail_before_loading_questions(self):
        for dataset, retrievers in [
            ("kestrel", ["dense", "unknown"]),
            ("kestrel", ["dense", "bm25", "unknown"]),
        ]:
            with self.subTest(dataset=dataset, retrievers=retrievers):
                with patch.object(runner, "load_questions") as load:
                    with self.assertRaisesRegex(ValueError, "supported retriever names"):
                        runner.run_evaluation(
                            dataset=dataset,
                            output_path="unused.jsonl",
                            retrievers=retrievers,
                        )
                load.assert_not_called()

    def test_invalid_settings_fail_before_loading_or_indexing(self):
        for options in [{"dataset": "unknown"}, {"top_k": 0}, {"top_k": 1.5},
                        {"top_k": True}, {"chunk_size": 1.5}, {"chunk_size": 0},
                        {"overlap": -1}, {"overlap": 800}, {"limit": 0},
                        {"limit": 1.5}, {"max_distance": float("nan")},
                        {"max_distance": 3}, {"max_distance": "bad"},
                        {"generate_answers": "false"}]:
            with self.subTest(options=options), patch.object(runner, "load_questions") as load:
                with self.assertRaises(ValueError):
                    runner.run_evaluation(**{"dataset": "baking", "output_path": "unused.jsonl", **options})
                load.assert_not_called()

    def test_threshold_filters_before_prefix_scoring(self):
        collection = SimpleNamespace(count=lambda: 2, query=lambda **kwargs: {
            "ids": [["close", "far"]], "documents": [["A fact.", "B fact."]],
            "metadatas": [[{"source": "guide.md", "position": 0}, {"source": "guide.md", "position": 1}]],
            "distances": [[0.1, 0.8]],
        })
        self.assertEqual([c["id"] for c in runner.retrieve(collection, "fact", 10, 0.5)], ["close"])
        self.assertEqual(len(runner.retrieve(collection, "fact", 10, None)), 2)

    def test_default_paths_separate_threshold_limit_and_generation(self):
        paths = []
        for changes in [{}, {"top_k": 3}, {"limit": 1}, {"max_distance": 0.5}, {"generate_answers": True}, {"retrievers": ["dense", "bm25"]}, {"generate_answers": True, "compare_path_context": True}]:
            args = SimpleNamespace(**{
                "dataset": "baking", "top_k": 5, "chunk_size": 800,
                "overlap": 80, "limit": None, "max_distance": None,
                "generate_answers": False, "compare_path_context": False, **changes,
            })
            with patch.object(runner, "run_evaluation") as run:
                runner.evaluate(args)
                paths.append(run.call_args.kwargs["output_path"])
        self.assertEqual(len(set(paths)), len(paths))

    def test_default_skips_generation_and_opt_in_calls_it(self):
        question = {
            "id": "test", "question": "What fact?", "type": "other",
            "answerable": True,
            "evidence": [{"source": "guide.md", "quote": "A fact."}],
        }
        chunks = [{"id": str(i), "source": "guide.md", "text": "A fact.",
                   "position": i, "distance": 0.2} for i in range(10)]
        for generate in [False, True]:
            with self.subTest(generate=generate), tempfile.TemporaryDirectory() as temp:
                output = Path(temp) / "results.jsonl"
                with contextlib.ExitStack() as stack:
                    stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                    stack.enter_context(patch.object(runner, "load_questions", return_value=[question]))
                    stack.enter_context(patch.object(runner, "load_documents", return_value=[
                        {"source": "guide.md", "text": "A fact."},
                    ]))
                    stack.enter_context(patch.object(runner, "build_isolated_index", return_value=(object(), 10)))
                    retrieve = stack.enter_context(patch.object(runner, "retrieve", return_value=chunks))
                    provider = stack.enter_context(patch.object(runner, "generate_answer", return_value=SimpleNamespace(
                        status="not_found", answer="No answer.", references=[],
                    )))
                    options = {"generate_answers": True} if generate else {}
                    self.assertEqual(runner.run_evaluation(
                        dataset="baking", top_k=3, output_path=output, **options,
                    ), output)
                    self.assertEqual(provider.call_count, int(generate))
                    if generate:
                        self.assertEqual(len(provider.call_args.args[1]), 3)
                    self.assertEqual(retrieve.call_args.args[2], 10)
                row = json.loads(output.read_text())
                self.assertEqual(row["generate_answers"], generate)
                self.assertEqual(row["retrievers"], ["dense"])
                self.assertFalse(row["compare_path_context"])
                self.assertEqual(row["status"], "not_found" if generate else "retrieval_only")
                self.assertEqual(len(row["retrieved_chunks"]), 3)
                self.assertEqual(row["retrieval_metrics"]["10"]["recall"], 1)
                self.assertGreaterEqual(
                    row["latency_ms"]["retrievers"]["dense"],
                    0,
                )
                self.assertGreaterEqual(row["latency_ms"]["retrieval_total"], 0)
                self.assertEqual(
                    row["latency_ms"]["generation_without_path_context"] is not None,
                    generate,
                )
                summary = json.loads(output.with_name("results_summary.jsonl").read_text())
                self.assertEqual(summary["generate_answers"], generate)
                self.assertEqual(
                    summary["latency_summary_ms"]["retrieval_total"]["samples"],
                    1,
                )
                if not generate:
                    self.assertIsNone(row["model_answer"])
                    self.assertIsNone(row["model"])

    def test_path_context_comparison_generates_paired_answers(self):
        question = {
            "id": "test",
            "question": "When is the launch window?",
            "type": "lookup",
            "answerable": True,
            "evidence": [{
                "source": "guide.md",
                "quote": "The Kestrel launch window is 2025.",
            }],
        }
        graph_chunk = {
            "id": "kestrel-1",
            "text": "The Kestrel launch window is 2025.",
            "source": "guide.md",
            "position": 0,
            "rank": 1,
            "retriever": "graph",
        }
        graph_path = {
            "hop_count": 1,
            "supporting_chunk_ids": ["kestrel-1"],
        }
        answers = [
            SimpleNamespace(status="answered", answer="2025.", references=[]),
            SimpleNamespace(status="answered", answer="2025, via graph.", references=[]),
        ]
        with tempfile.TemporaryDirectory() as temp, contextlib.ExitStack() as stack:
            output = Path(temp) / "path-context.jsonl"
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            stack.enter_context(patch.object(runner, "load_questions", return_value=[question]))
            stack.enter_context(patch.object(runner, "load_documents", return_value=[
                {"source": "guide.md", "text": "The Kestrel launch window is 2025."},
            ]))
            stack.enter_context(patch.object(
                runner,
                "retrieve_graph",
                return_value={"chunks": [graph_chunk], "paths": [graph_path]},
            ))
            provider = stack.enter_context(patch.object(
                runner,
                "generate_answer",
                side_effect=answers,
            ))

            runner.run_evaluation(
                dataset="kestrel",
                retrievers=["graph"],
                generate_answers=True,
                compare_path_context=True,
                output_path=output,
            )

            row = json.loads(output.read_text())
            summary = json.loads(
                output.with_name("path-context_summary.jsonl").read_text()
            )

        self.assertEqual(provider.call_count, 2)
        self.assertEqual(provider.call_args_list[0].args[1], provider.call_args_list[1].args[1])
        self.assertNotIn("path_context", provider.call_args_list[0].kwargs)
        from backend.schemas import PathContext

        self.assertIsInstance(
            provider.call_args_list[1].kwargs["path_context"],
            PathContext,
        )
        self.assertEqual(
            row["path_context_comparison"]["without_path_context"]["model_answer"],
            "2025.",
        )
        self.assertEqual(
            row["path_context_comparison"]["with_path_context"]["model_answer"],
            "2025, via graph.",
        )
        self.assertGreaterEqual(
            row["latency_ms"]["generation_without_path_context"],
            0,
        )
        self.assertGreaterEqual(
            row["latency_ms"]["generation_with_path_context"],
            0,
        )
        self.assertEqual(
            summary["latency_summary_ms"]["generation_with_path_context"]["samples"],
            1,
        )

    def test_path_context_comparison_marks_missing_paths_unavailable(self):
        question = {
            "id": "test",
            "question": "When is the launch window?",
            "type": "lookup",
            "answerable": False,
            "evidence": [],
        }
        answer = SimpleNamespace(status="not_found", answer="No answer.", references=[])
        with tempfile.TemporaryDirectory() as temp, contextlib.ExitStack() as stack:
            output = Path(temp) / "no-path.jsonl"
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            stack.enter_context(patch.object(runner, "load_questions", return_value=[question]))
            stack.enter_context(patch.object(runner, "load_documents", return_value=[
                {"source": "guide.md", "text": "Some unrelated document."},
            ]))
            stack.enter_context(patch.object(
                runner,
                "retrieve_graph",
                return_value={"chunks": [], "paths": []},
            ))
            provider = stack.enter_context(patch.object(
                runner,
                "generate_answer",
                return_value=answer,
            ))

            runner.run_evaluation(
                dataset="kestrel",
                retrievers=["graph"],
                generate_answers=True,
                compare_path_context=True,
                output_path=output,
            )

            row = json.loads(output.read_text())

        provider.assert_called_once()
        self.assertEqual(
            row["path_context_comparison"]["with_path_context"]["status"],
            "not_available",
        )
        self.assertIsNone(
            row["latency_ms"]["generation_with_path_context"]
        )


if __name__ == "__main__":
    unittest.main()
