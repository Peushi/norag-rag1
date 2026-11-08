import unittest

from backend.retrieval_orchestrator import (
    RetrievalQuery,
    RetrieverOutput,
    orchestrate_retrieval,
)


def chunk(chunk_id: str, rank: int, retriever: str) -> dict:
    return {
        "id": chunk_id,
        "text": f"Text for {chunk_id}",
        "source": "guide.md",
        "position": 0,
        "rank": rank,
        "retriever": retriever,
    }


class RetrievalOrchestratorTests(unittest.TestCase):
    def test_runs_enabled_retrievers_and_fuses_results(self):
        calls = []

        def make_retriever(name, results):
            def retrieve(query):
                calls.append((name, query))
                return RetrieverOutput(chunks=results)

            return retrieve

        query = RetrievalQuery(
            question="Where is the item?",
            dataset="kestrel",
            top_k=5,
            document_ids=("manual.md",),
            chunk_size=400,
            overlap=40,
        )
        result = orchestrate_retrieval(
            query,
            ("dense", "bm25"),
            {
                "dense": make_retriever(
                    "dense",
                    [chunk("shared", 1, "dense"), chunk("dense-only", 2, "dense")],
                ),
                "bm25": make_retriever(
                    "bm25",
                    [chunk("shared", 2, "bm25"), chunk("bm25-only", 1, "bm25")],
                ),
                "graph": make_retriever("graph", []),
            },
            final_top_k=2,
        )

        self.assertEqual([name for name, _ in calls], ["dense", "bm25"])
        self.assertTrue(all(called_query is query for _, called_query in calls))
        self.assertEqual(result.retrievers, ("dense", "bm25"))
        self.assertEqual([item["id"] for item in result.chunks], ["shared", "bm25-only"])
        self.assertEqual([item["final_rank"] for item in result.chunks], [1, 2])
        self.assertEqual(result.graph_paths, [])

    def test_preserves_graph_paths_when_graph_is_enabled(self):
        paths = [
            {
                "entities": ["Person A", "Location B"],
                "edges": [{"relation": "VISITED"}],
                "supporting_chunk_ids": ["chunk-1"],
            }
        ]
        result = orchestrate_retrieval(
            RetrievalQuery(
                question="Where did Person A go?",
                dataset="kestrel",
                top_k=2,
            ),
            ("graph",),
            {
                "graph": lambda query: RetrieverOutput(
                    chunks=[chunk("chunk-1", 1, "graph")],
                    graph_paths=paths,
                )
            },
        )

        self.assertEqual(result.graph_paths, paths)
        self.assertEqual(result.retrievers, ("graph",))

    def test_rejects_all_retrievers_disabled(self):
        with self.assertRaisesRegex(ValueError, "At least one retriever"):
            orchestrate_retrieval(
                RetrievalQuery("question", "baking", 3),
                (),
                {},
            )

    def test_rejects_unregistered_retriever(self):
        with self.assertRaisesRegex(ValueError, "No implementation registered"):
            orchestrate_retrieval(
                RetrievalQuery("question", "baking", 3),
                ("bm25",),
                {},
            )

    def test_rejects_graph_for_baking(self):
        with self.assertRaisesRegex(ValueError, "only available for the kestrel"):
            orchestrate_retrieval(
                RetrievalQuery("question", "baking", 3),
                ("graph",),
                {"graph": lambda query: RetrieverOutput(chunks=[])},
            )

    def test_rejects_duplicate_retriever_selection(self):
        with self.assertRaisesRegex(ValueError, "cannot contain duplicates"):
            orchestrate_retrieval(
                RetrievalQuery("question", "kestrel", 3),
                ("dense", "dense"),
                {"dense": lambda query: RetrieverOutput(chunks=[])},
            )

    def test_propagates_retriever_errors(self):
        def failing_retriever(query):
            raise RuntimeError("index unavailable")

        with self.assertRaisesRegex(RuntimeError, "index unavailable"):
            orchestrate_retrieval(
                RetrievalQuery("question", "baking", 3),
                ("dense",),
                {"dense": failing_retriever},
            )

    def test_rejects_invalid_chunking_settings_before_dispatch(self):
        calls = []
        with self.assertRaisesRegex(ValueError, "overlap"):
            orchestrate_retrieval(
                RetrievalQuery(
                    "question",
                    "baking",
                    3,
                    chunk_size=100,
                    overlap=100,
                ),
                ("dense",),
                {
                    "dense": lambda query: (
                        calls.append(query) or RetrieverOutput(chunks=[])
                    )
                },
            )
        self.assertEqual(calls, [])

    def test_rejects_invalid_retriever_output(self):
        with self.assertRaisesRegex(TypeError, "must return RetrieverOutput"):
            orchestrate_retrieval(
                RetrievalQuery("question", "baking", 3),
                ("dense",),
                {"dense": lambda query: []},
            )


if __name__ == "__main__":
    unittest.main()
