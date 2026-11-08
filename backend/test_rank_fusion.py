import unittest

from backend.rank_fusion import RRF_CONSTANT, reciprocal_rank_fusion


def chunk(
    chunk_id: str,
    rank: int,
    retriever: str,
    *,
    score: float | None = None,
    score_type: str | None = None,
) -> dict:
    result = {
        "id": chunk_id,
        "text": f"Text for {chunk_id}",
        "source": "guide.md",
        "position": 0,
        "rank": rank,
        "retriever": retriever,
    }
    if score is not None:
        result["score"] = score
        result["score_type"] = score_type
    return result


class ReciprocalRankFusionTests(unittest.TestCase):
    def test_fuses_by_rank_and_preserves_each_retriever_contribution(self):
        fused = reciprocal_rank_fusion(
            {
                "dense": [
                    chunk(
                        "shared",
                        3,
                        "dense",
                        score=0.2,
                        score_type="cosine_distance",
                    ),
                    chunk("dense-only", 1, "dense"),
                ],
                "bm25": [
                    chunk(
                        "shared",
                        1,
                        "bm25",
                        score=4.5,
                        score_type="bm25",
                    ),
                    chunk("bm25-only", 2, "bm25"),
                ],
            }
        )

        self.assertEqual(
            [result["id"] for result in fused],
            ["shared", "dense-only", "bm25-only"],
        )
        self.assertEqual([item["final_rank"] for item in fused], [1, 2, 3])
        self.assertAlmostEqual(
            fused[0]["final_score"],
            1 / (RRF_CONSTANT + 3) + 1 / (RRF_CONSTANT + 1),
        )
        self.assertEqual(
            fused[0]["retrievers"],
            [
                {
                    "retriever": "bm25",
                    "rank": 1,
                    "score": 4.5,
                    "score_type": "bm25",
                },
                {
                    "retriever": "dense",
                    "rank": 3,
                    "score": 0.2,
                    "score_type": "cosine_distance",
                },
            ],
        )
        self.assertNotIn("score", fused[0])

    def test_breaks_equal_scores_by_chunk_id(self):
        fused = reciprocal_rank_fusion(
            {
                "dense": [
                    chunk("chunk-a", 1, "dense"),
                    chunk("chunk-b", 2, "dense"),
                ],
                "bm25": [
                    chunk("chunk-a", 2, "bm25"),
                    chunk("chunk-b", 1, "bm25"),
                ],
            }
        )

        self.assertEqual(
            [(item["id"], item["final_rank"]) for item in fused],
            [("chunk-a", 1), ("chunk-b", 2)],
        )

    def test_returns_empty_for_no_retriever_results(self):
        self.assertEqual(reciprocal_rank_fusion({"dense": [], "bm25": []}), [])
        self.assertEqual(reciprocal_rank_fusion({}), [])

    def test_single_retriever_preserves_rank_order(self):
        fused = reciprocal_rank_fusion(
            {
                "graph": [
                    chunk("first", 1, "graph"),
                    chunk("second", 2, "graph"),
                ],
            }
        )

        self.assertEqual([item["id"] for item in fused], ["first", "second"])
        self.assertEqual([item["final_rank"] for item in fused], [1, 2])

    def test_respects_top_k_after_fusion(self):
        fused = reciprocal_rank_fusion(
            {
                "dense": [
                    chunk("first", 1, "dense"),
                    chunk("second", 2, "dense"),
                ],
            },
            top_k=1,
        )

        self.assertEqual([item["id"] for item in fused], ["first"])
        self.assertEqual(fused[0]["final_rank"], 1)

    def test_rejects_repeated_chunk_from_one_retriever(self):
        duplicate = chunk("same", 1, "dense")
        with self.assertRaisesRegex(ValueError, "more than once"):
            reciprocal_rank_fusion({"dense": [duplicate, duplicate]})

    def test_rejects_conflicting_content_for_same_chunk_id(self):
        dense_chunk = chunk("shared", 1, "dense")
        bm25_chunk = chunk("shared", 1, "bm25")
        bm25_chunk["text"] = "Different chunk text"

        with self.assertRaisesRegex(ValueError, "conflicting content"):
            reciprocal_rank_fusion(
                {"dense": [dense_chunk], "bm25": [bm25_chunk]}
            )

    def test_requires_score_and_score_type_together(self):
        invalid_chunk = chunk("scored", 1, "dense", score=0.2)
        invalid_chunk.pop("score_type")
        with self.assertRaisesRegex(ValueError, "both score and score_type"):
            reciprocal_rank_fusion({"dense": [invalid_chunk]})

    def test_rejects_invalid_top_k(self):
        with self.assertRaisesRegex(ValueError, "top_k must be a positive"):
            reciprocal_rank_fusion({}, top_k=0)


if __name__ == "__main__":
    unittest.main()
