import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.llm_service import generate_answer
from backend.main import app
from backend.rag_service import _build_path_context, ask_question
from backend.retrieval_orchestrator import OrchestratedRetrieval
from backend.schemas import AskRequest, AskResponse, PathContext


class PathContextSchemaTests(unittest.TestCase):
    def test_path_context_requires_graph_retrieval(self):
        with self.assertRaisesRegex(ValueError, "requires graph retrieval"):
            AskRequest(
                question="Where did the person go?",
                retrievers=["dense"],
                include_path_context=True,
            )

    def test_path_context_can_be_enabled_with_graph(self):
        request = AskRequest(
            question="Where did the person go?",
            retrievers=["dense", "graph"],
            include_path_context=True,
        )
        self.assertTrue(request.include_path_context)


class PathContextBuildingTests(unittest.TestCase):
    def test_builds_context_from_paths_and_original_graph_chunks(self):
        paths = [
            {
                "entities": ["Person A", "Location B"],
                "edges": [{"relation": "VISITED"}],
                "supporting_chunk_ids": ["chunk-1"],
            }
        ]
        chunks = [
            {
                "id": "chunk-1",
                "text": "Person A visited Location B.",
                "source": "story.txt",
                "position": 4,
                "rank": 1,
                "retriever": "graph",
            }
        ]

        context = _build_path_context(paths, chunks)

        self.assertIsInstance(context, PathContext)
        self.assertEqual(context.paths, paths)
        self.assertEqual(
            [chunk.model_dump() for chunk in context.supporting_chunks],
            [
                {
                    "chunk_id": "chunk-1",
                    "source": "story.txt",
                    "position": 4,
                    "text": "Person A visited Location B.",
                }
            ],
        )

    def test_deduplicates_chunks_referenced_by_multiple_paths(self):
        path = {"supporting_chunk_ids": ["chunk-1"]}
        context = _build_path_context(
            [path, path],
            [
                {
                    "id": "chunk-1",
                    "text": "Evidence.",
                    "source": "story.txt",
                    "position": 0,
                }
            ],
        )

        self.assertEqual(len(context.supporting_chunks), 1)

    def test_rejects_paths_with_missing_supporting_chunks(self):
        with self.assertRaisesRegex(ValueError, "unavailable supporting chunk"):
            _build_path_context(
                [{"supporting_chunk_ids": ["missing"]}],
                [],
            )

    def test_returns_none_when_no_graph_paths_exist(self):
        self.assertIsNone(_build_path_context([], []))


class PathContextAskFlowTests(unittest.TestCase):
    def test_ask_passes_optional_context_to_generation_and_response(self):
        retrieval = OrchestratedRetrieval(
            chunks=[
                {
                    "id": "answer-chunk",
                    "text": "Answer evidence.",
                    "source": "story.txt",
                    "position": 0,
                    "final_rank": 1,
                    "final_score": 1 / 61,
                    "retrievers": [{"retriever": "graph", "rank": 1}],
                }
            ],
            graph_paths=[
                {
                    "entities": ["Person A", "Location B"],
                    "edges": [{"relation": "VISITED"}],
                    "supporting_chunk_ids": ["answer-chunk"],
                }
            ],
            retrievers=("graph",),
            graph_chunks=[
                {
                    "id": "answer-chunk",
                    "text": "Answer evidence.",
                    "source": "story.txt",
                    "position": 0,
                    "rank": 1,
                    "retriever": "graph",
                }
            ],
        )
        with (
            patch("backend.rag_service.retrieve_selected_chunks", return_value=retrieval),
            patch(
                "backend.rag_service.generate_answer",
                return_value=SimpleNamespace(model_copy=lambda *, update: update),
            ) as generate,
        ):
            result = ask_question(
                "Where did Person A go?",
                retrievers=["graph"],
                include_path_context=True,
            )

        passed_context = generate.call_args.kwargs["path_context"]
        self.assertIsInstance(passed_context, PathContext)
        self.assertEqual(
            passed_context.supporting_chunks[0].chunk_id,
            "answer-chunk",
        )
        self.assertEqual(result["retrieval"].path_context, passed_context)

    def test_ask_without_path_context_preserves_default_generation_call(self):
        retrieval = OrchestratedRetrieval(
            chunks=[],
            graph_paths=[],
            retrievers=("dense",),
        )
        with (
            patch("backend.rag_service.retrieve_selected_chunks", return_value=retrieval),
            patch(
                "backend.rag_service.generate_answer",
                return_value=SimpleNamespace(model_copy=lambda *, update: update),
            ) as generate,
        ):
            ask_question("Question?", retrievers=["dense"])

        self.assertIsNone(generate.call_args.kwargs["path_context"])

    def test_ask_api_rejects_path_context_without_graph(self):
        response = TestClient(app).post(
            "/api/ask",
            json={
                "question": "Where did Person A go?",
                "retrievers": ["dense"],
                "include_path_context": True,
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_ask_api_passes_path_context_option_to_service(self):
        answer = AskResponse(
            status="not_found",
            answer="No supporting evidence.",
        )
        with patch("backend.main.ask_question", return_value=answer) as ask:
            response = TestClient(app).post(
                "/api/ask",
                json={
                    "question": "Where did Person A go?",
                    "retrievers": ["graph"],
                    "include_path_context": True,
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(ask.call_args.kwargs["include_path_context"])


class PathContextPromptTests(unittest.TestCase):
    def test_generation_includes_path_and_support_chunks_for_citations(self):
        captured = {}
        path_context = PathContext(
            paths=[
                {
                    "entities": ["Person A", "Location B"],
                    "edges": [{"relation": "VISITED"}],
                    "supporting_chunk_ids": ["path-chunk"],
                }
            ],
            supporting_chunks=[
                {
                    "chunk_id": "path-chunk",
                    "source": "story.txt",
                    "position": 2,
                    "text": "Person A visited Location B.",
                }
            ],
        )

        def fake_create(**kwargs):
            captured["prompt"] = kwargs["messages"][1]["content"]
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=json.dumps(
                                {
                                    "status": "answered",
                                    "answer": "Person A went to Location B.",
                                    "cited_chunk_ids": ["path-chunk"],
                                }
                            )
                        )
                    )
                ]
            )

        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=fake_create),
            )
        )
        with patch("backend.llm_service.client", fake_client):
            answer = generate_answer(
                "Where did Person A go?",
                [
                    {
                        "id": "dense-chunk",
                        "source": "story.txt",
                        "position": 1,
                        "text": "A related passage.",
                    }
                ],
                path_context=path_context,
            )

        self.assertEqual(answer.status, "answered")
        self.assertEqual(answer.references[0].chunk_id, "path-chunk")
        self.assertEqual(answer.references[0].position, 2)
        self.assertIn('"VISITED"', captured["prompt"])
        self.assertIn("Person A visited Location B.", captured["prompt"])
        self.assertIn("Graph paths are extracted claims", captured["prompt"])

    def test_generation_without_path_context_does_not_add_graph_section(self):
        from backend.llm_service import build_prompt

        prompt = build_prompt("Question?", [])
        self.assertNotIn("GRAPH PATHS", prompt)


if __name__ == "__main__":
    unittest.main()
