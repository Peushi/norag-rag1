import unittest

from evaluation.retrieval_metrics import match_evidence, score_at_k, summarize_metrics


class RetrievalMetricTests(unittest.TestCase):
    def test_rank_cutoffs_and_no_double_counting(self):
        scores = score_at_k([
            {"matched_chunks": [{"id": "a", "rank": 1}, {"id": "b", "rank": 3}]},
            {"matched_chunks": [{"id": "c", "rank": 5}]},
            {"matched_chunks": [{"id": "d", "rank": 10}]},
        ])
        for k, recovered in [("1", 1), ("3", 1), ("5", 2), ("10", 3)]:
            self.assertTrue(scores[k]["hit"])
            self.assertEqual(scores[k]["matched_evidence"], recovered)
            self.assertAlmostEqual(scores[k]["recall"], recovered / 3)

    def test_miss_and_unanswerable(self):
        self.assertIsNone(score_at_k(None))
        scores = score_at_k([{"matched_chunks": []}])
        self.assertFalse(scores["10"]["hit"])
        self.assertEqual(scores["10"]["recall"], 0)

    def test_macro_averages_per_type_and_exclusion(self):
        rows = [
            {"type": "split_answer", "retrieval_metrics": score_at_k([
                {"matched_chunks": [{"rank": 1}]}, {"matched_chunks": []},
            ])},
            {"type": "vocabulary", "retrieval_metrics": score_at_k([
                {"matched_chunks": []},
            ])},
            {"type": "not_in_corpus", "retrieval_metrics": None},
        ]
        summary = summarize_metrics(rows)
        self.assertEqual(summary["overall"]["answerable_questions"], 2)
        self.assertEqual(summary["overall"]["excluded_questions"], 1)
        self.assertEqual(summary["overall"]["metrics"]["5"], {"hit_rate": 0.5, "recall": 0.25})
        self.assertEqual(summary["by_type"]["split_answer"]["metrics"]["5"]["recall"], 0.5)
        self.assertIsNone(summary["by_type"]["not_in_corpus"]["metrics"]["5"]["hit_rate"])
        self.assertIsNone(summarize_metrics([])["overall"]["metrics"]["1"]["recall"])


class EvidenceMatchingTests(unittest.TestCase):
    def score(self, evidence, chunks, text="First fact. Second fact.", **settings):
        return match_evidence(
            {"id": "test", "answerable": True, "evidence": evidence},
            chunks,
            [{"source": "guide.md", "text": text}],
            chunk_size=settings.get("chunk_size", 100),
            overlap=settings.get("overlap", 0),
        )

    def test_source_alone_is_not_a_match(self):
        result = self.score(
            [{"source": "guide.md", "quote": "First fact."}],
            [{"id": "wrong-passage", "source": "guide.md", "text": "Second fact."},
             {"id": "wrong-source", "source": "other.md", "text": "First fact."}],
        )
        self.assertEqual(result[0]["matched_chunks"], [])
        self.assertFalse(result[0]["boundary_split"])

    def test_whitespace_and_multiple_chunk_matches(self):
        result = self.score(
            [{"source": "guide.md", "quote": "First fact."}],
            [{"id": "a", "source": "guide.md", "text": "First\n fact."},
             {"id": "b", "source": "guide.md", "text": "First fact."}],
        )
        self.assertEqual(result[0]["matched_chunks"], [
            {"id": "a", "rank": 1}, {"id": "b", "rank": 2},
        ])

    def test_multiple_evidence_items_are_kept_separate(self):
        result = self.score(
            [{"source": "guide.md", "quote": "First fact."},
             {"source": "guide.md", "quote": "Second fact."}],
            [{"id": "a", "source": "guide.md", "text": "First fact."}],
        )
        self.assertEqual(len(result), 2)
        self.assertTrue(result[0]["matched_chunks"])
        self.assertEqual(result[1]["matched_chunks"], [])

    def test_split_quote_is_flagged_without_joining_chunks(self):
        result = self.score(
            [{"source": "guide.md", "quote": "defghi"}],
            [{"id": "a", "source": "guide.md", "text": "abcdef"},
             {"id": "b", "source": "guide.md", "text": "ghijkl"}],
            text="abcdefghijkl", chunk_size=6,
        )
        self.assertTrue(result[0]["boundary_split"])
        self.assertEqual(result[0]["matched_chunks"], [])

    def test_unanswerable_is_excluded(self):
        self.assertIsNone(match_evidence(
            {"answerable": False, "evidence": []}, [], [], chunk_size=100, overlap=0,
        ))

    def test_missing_or_invalid_labels_fail_explicitly(self):
        for evidence in [[], [None], [{}], [{"source": "guide.md"}],
                         [{"source": "guide.md", "quote": 12}],
                         [{"source": "guide.md", "quote": ""}],
                         [{"source": "guide.md", "quote": "Not here"}],
                         [{"source": "missing.md", "quote": "First fact."}]]:
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                self.score(evidence, [])

    def test_answerable_label_must_be_explicit_and_consistent(self):
        for question in [{}, {"answerable": "false"},
                         {"answerable": False, "evidence": [{"quote": "x"}]}]:
            with self.subTest(question=question), self.assertRaises(ValueError):
                match_evidence(question, [], [], chunk_size=100, overlap=0)

    def test_duplicate_chunks_do_not_inflate_recall(self):
        chunk = {"id": "same", "source": "guide.md", "text": "First fact."}
        matches = self.score(
            [{"source": "guide.md", "quote": "First fact."},
             {"source": "guide.md", "quote": "Second fact."}],
            [chunk, chunk],
        )
        self.assertEqual(score_at_k(matches)["5"]["recall"], 0.5)

    def test_whitespace_does_not_change_case_punctuation_or_words(self):
        for text in ["first fact.", "First fact!", "First fiction."]:
            with self.subTest(text=text):
                matches = self.score(
                    [{"source": "guide.md", "quote": "First fact."}],
                    [{"id": "a", "source": "guide.md", "text": text}],
                )
                self.assertFalse(score_at_k(matches)["10"]["hit"])


if __name__ == "__main__":
    unittest.main()
