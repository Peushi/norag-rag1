import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.rag_service import retrieve_selected_chunks
from backend.retrieval_orchestrator import OrchestratedRetrieval
from backend.schemas import AskResponse, RetrieveRequest, RetrievedChunk


class RetrieverSelectionSchemaTests(unittest.TestCase):
    def test_dense_is_the_default_retriever(self):
        request = RetrieveRequest(question="What happened?")
        self.assertEqual(request.retrievers, ["dense"])

    def test_rejects_empty_retriever_selection(self):
        with self.assertRaises(ValueError):
            RetrieveRequest(question="What happened?", retrievers=[])

    def test_rejects_duplicate_retrievers(self):
        with self.assertRaisesRegex(ValueError, "cannot contain duplicates"):
            RetrieveRequest(
                question="What happened?",
                retrievers=["dense", "dense"],
            )

    def test_rejects_unknown_retriever_name(self):
        with self.assertRaises(ValueError):
            RetrieveRequest(question="What happened?", retrievers=["keyword"])


class RetrieverSelectionApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_retrieve_endpoint_returns_fused_contract(self):
        retrieval = OrchestratedRetrieval(
            chunks=[
                {
                    "id": "chunk-1",
                    "text": "Supporting text",
                    "source": "guide.md",
                    "position": 0,
                    "final_rank": 1,
                    "final_score": 1 / 61,
                    "retrievers": [
                        {
                            "retriever": "dense",
                            "rank": 1,
                            "score": 0.1,
                            "score_type": "cosine_distance",
                        }
                    ],
                }
            ],
            graph_paths=[],
            retrievers=("dense",),
        )
        with patch(
            "backend.main.retrieve_selected_chunks",
            return_value=retrieval,
        ) as retrieve:
            response = self.client.post(
                "/api/retrieve",
                json={"question": "What happened?"},
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["retrievers"], ["dense"])
        self.assertEqual(response.json()["chunks"][0]["final_rank"], 1)
        self.assertEqual(
            response.json()["chunks"][0]["retrievers"][0]["score_type"],
            "cosine_distance",
        )
        self.assertEqual(retrieve.call_args.kwargs["retrievers"], ["dense"])

    def test_retrieve_endpoint_rejects_empty_selection(self):
        response = self.client.post(
            "/api/retrieve",
            json={"question": "What happened?", "retrievers": []},
        )
        self.assertEqual(response.status_code, 422)

    def test_retrieve_endpoint_supports_bm25(self):
        with patch("backend.bm25.load_documents", return_value=[
            {"source": "guide.md", "text": "What happened?"},
        ]):
            response = self.client.post(
                "/api/retrieve",
                json={"question": "What happened?", "retrievers": ["bm25"]},
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["chunks"][0]["retrievers"][0]["score_type"], "bm25")

    def test_ask_endpoint_passes_selected_retrievers(self):
        answer = AskResponse(
            status="not_found",
            answer="No supporting evidence.",
            references=[],
        )
        with patch("backend.main.ask_question", return_value=answer) as ask:
            response = self.client.post(
                "/api/ask",
                json={
                    "question": "What happened?",
                    "dataset": "kestrel",
                    "retrievers": ["dense", "graph"],
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            ask.call_args.kwargs["retrievers"],
            ["dense", "graph"],
        )
        self.assertEqual(ask.call_args.kwargs["dataset"], "kestrel")

    def test_ask_endpoint_reports_unimplemented_graph(self):
        response = self.client.post(
            "/api/ask",
            json={"question": "What happened?", "retrievers": ["graph"]},
        )
        self.assertEqual(response.status_code, 501)
        self.assertIn("graph", response.json()["error"]["message"])


class DenseRetrieverAdapterTests(unittest.TestCase):
    def test_dense_results_are_normalized_before_fusion(self):
        chunks = [
            RetrievedChunk(
                id="chunk-1",
                text="Supporting text",
                source="guide.md",
                position=2,
                distance=0.15,
            )
        ]
        with patch(
            "backend.rag_service.retrieve_chunks",
            return_value=chunks,
        ) as retrieve:
            retrieval = retrieve_selected_chunks(
                "What happened?",
                retrievers=["dense"],
                document_ids=["guide.md"],
                top_k=4,
                dataset="kestrel",
            )

        self.assertEqual(retrieve.call_args.kwargs["dataset"], "kestrel")
        self.assertEqual(retrieval.retrievers, ("dense",))
        self.assertEqual(
            retrieval.chunks,
            [
                {
                    "id": "chunk-1",
                    "text": "Supporting text",
                    "source": "guide.md",
                    "position": 2,
                    "final_rank": 1,
                    "final_score": 1 / 61,
                    "retrievers": [
                        {
                            "retriever": "dense",
                            "rank": 1,
                            "score": 0.15,
                            "score_type": "cosine_distance",
                        }
                    ],
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
