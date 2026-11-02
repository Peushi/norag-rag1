import unittest
from unittest.mock import patch

from backend.schemas import (
    WordChunksResponse,
    WordQuestionAnalysisResponse,
    WordVocabularyResponse,
)
from backend.words_analytics import analyze_question, get_vocabulary, get_word_chunks


class WordsAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.documents = [
            {
                "source": "notes.md",
                "text": "bread bread bread bread KST-2044",
            }
        ]
        self.documents_patcher = patch(
            "backend.words_analytics.load_documents",
            return_value=self.documents,
        )
        self.documents_patcher.start()

    def tearDown(self):
        self.documents_patcher.stop()

    def test_vocabulary_counts_source_occurrences_and_distinct_chunks(self):
        result = get_vocabulary(
            "baking",
            chunk_size=16,
            overlap=8,
            limit=500,
        )
        bread = next(word for word in result["words"] if word["word"] == "bread")

        self.assertEqual(bread["occurrence_count"], 4)
        self.assertEqual(bread["chunk_count"], 3)
        WordVocabularyResponse.model_validate(result)

    def test_selected_word_reports_per_chunk_counts(self):
        result = get_word_chunks(
            "baking",
            "BREAD",
            chunk_size=16,
            overlap=8,
        )

        self.assertEqual(result["word"], "bread")
        self.assertEqual(result["occurrence_count"], 4)
        self.assertEqual(result["chunk_count"], 3)
        self.assertEqual(
            sum(chunk["occurrence_count"] for chunk in result["chunks"]),
            5,
        )
        self.assertTrue(all(chunk["chunk_id"] for chunk in result["chunks"]))
        WordChunksResponse.model_validate(result)

    def test_question_analysis_normalizes_case_and_splits_identifier(self):
        result = analyze_question(
            "baking",
            "BREAD, flour? KST-2044",
        )

        found = {entry["word"]: entry for entry in result["words_found"]}
        self.assertEqual(found["bread"]["occurrence_count"], 4)
        self.assertIn("kst", found)
        self.assertIn("2044", found)
        self.assertEqual(result["words_missing"], ["flour"])
        self.assertEqual(
            {word for chunk in result["matching_chunks"] for word in chunk["matched_words"]},
            {"bread", "kst", "2044"},
        )
        WordQuestionAnalysisResponse.model_validate(result)

    def test_punctuation_and_case_are_normalized_consistently(self):
        result = analyze_question("baking", "BREAD bread, KST-2044.")
        found_words = [entry["word"] for entry in result["words_found"]]
        self.assertEqual(found_words, ["bread", "kst", "2044"])


if __name__ == "__main__":
    unittest.main()
