import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.bm25 import BM25Index, retrieve_bm25
from backend.chunking import chunk_text
from backend.main import app
from backend.retrieval import DATASET_DIRECTORIES, make_chunk_id
from backend.retrieval_orchestrator import RetrievalQuery
from backend.schemas import FusedRetrievedChunk


def doc(source, text):
    return {"source": source, "text": text}


class BM25ScoringTests(unittest.TestCase):
    def test_tokenizer_case_punctuation_identifiers_numbers_and_whole_words(self):
        index = BM25Index([doc("a.md", "Bread, KST-2044! 123"), doc("b.md", "breadboard")])
        for query in ["BREAD", "2044", "kst-2044", "123"]:
            with self.subTest(query=query):
                self.assertEqual([c["source"] for c in index.search(query)], ["a.md"])

    def test_hand_calculated_score(self):
        index = BM25Index([doc("a.md", "rare common"), doc("b.md", "common common")])
        # N=2, df(rare)=1, tf=1 and length=average length => TF factor is 1.
        self.assertAlmostEqual(index.search("rare")[0]["score"], math.log(2))
        self.assertGreater(index.search("rare")[0]["score"], index.search("common")[1]["score"])

    def test_term_frequency_increases_score_with_saturation(self):
        index = BM25Index([doc("a.md", "apple filler filler filler"),
                           doc("b.md", "apple apple filler filler")])
        results = index.search("apple")
        self.assertEqual(results[0]["source"], "b.md")
        self.assertGreater(results[0]["score"], results[1]["score"])
        self.assertLess(results[0]["score"], 2 * results[1]["score"])

    def test_length_normalization_favors_shorter_document_for_same_tf(self):
        index = BM25Index([doc("short.md", "apple"), doc("long.md", "apple filler filler filler")])
        self.assertEqual(index.search("apple")[0]["source"], "short.md")

    def test_duplicate_query_terms_do_not_change_scores(self):
        index = BM25Index([doc("a.md", "bread bread flour")])
        self.assertEqual(index.search("bread"), index.search("bread BREAD bread"))

    def test_equal_scores_tie_by_id_and_ranks_start_at_one(self):
        documents = [doc("a.md", "bread"), doc("b.md", "bread")]
        results = BM25Index(documents).search("bread", 20)
        self.assertEqual([r["id"] for r in results], sorted(r["id"] for r in results))
        self.assertEqual([r["rank"] for r in results], [1, 2])
        self.assertEqual(results, BM25Index(list(reversed(documents))).search("bread", 20))

    def test_empty_unknown_and_invalid_queries(self):
        for documents in [[], [doc("a.md", "bread")], [doc("a.md", "!!!")]]:
            index = BM25Index(documents)
            self.assertEqual(index.search("unseen"), [])
            self.assertEqual(index.search("!!!"), [])
            for query in ["", " \n", None]:
                with self.subTest(query=query), self.assertRaises(ValueError):
                    index.search(query)
        for top_k in [0, -1, 1.5, True]:
            with self.assertRaises(ValueError):
                BM25Index([]).search("bread", top_k)

    def test_top_k_filters_and_scores_use_corpus_statistics(self):
        index = BM25Index([doc("a.md", "bread"), doc("b.md", "bread flour")])
        full = index.search("bread", 100)
        self.assertEqual(len(index.search("bread", 1)), 1)
        self.assertEqual(index.search("bread", selected_documents=[]), [])
        self.assertEqual(index.search("bread", selected_documents=["missing.md"]), [])
        filtered = index.search("bread", selected_documents=["b.md"])
        self.assertEqual(filtered[0]["score"], next(c["score"] for c in full if c["source"] == "b.md"))

    def test_ids_and_text_match_shared_chunking_at_both_settings(self):
        text = "bread flour " * 100
        for size, overlap in [(800, 80), (400, 40)]:
            index = BM25Index([doc("bread/a.md", text)], size, overlap)
            expected = chunk_text(text, size, overlap)
            self.assertEqual([c["text"] for c in index.chunks], [c["text"] for c in expected])
            self.assertEqual([c["id"] for c in index.chunks],
                             [make_chunk_id("bread/a.md", c["position"]) for c in expected])
            self.assertTrue(all(c["retriever"] == c["score_type"] == "bm25"
                                and c["score"] > 0 for c in index.search("bread")))


class BM25IntegrationTests(unittest.TestCase):
    def test_real_dense_and_bm25_follow_documents_and_chunk_settings(self):
        import chromadb
        from backend import documents, rag_service, vector_store
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "corpus"
            root.mkdir()
            (root / "a.md").write_text("bread flour " * 30)
            client = chromadb.PersistentClient(path=str(Path(temp) / "db"))
            settings = SimpleNamespace(chunk_size=100, overlap=0, top_k=5, relevance_threshold=None)
            with patch.object(vector_store, "_client", client), \
                 patch.dict(DATASET_DIRECTORIES, {"baking": root}), \
                 patch.object(documents, "CORPUS_DIR", root), \
                 patch.object(rag_service, "APP_SETTINGS", settings):
                def verify_snapshot():
                    result = rag_service.retrieve_selected_chunks("bread", retrievers=["dense", "bm25"])
                    stored = vector_store.get_collection().get(include=["documents"])
                    fresh = BM25Index(documents.load_documents(root), settings.chunk_size, settings.overlap)
                    self.assertEqual(dict(zip(stored["ids"], stored["documents"])),
                                     {c["id"]: c["text"] for c in fresh.chunks})
                    return result
                self.assertTrue(verify_snapshot().chunks)
                (root / "a.md").write_text("bread butter " * 40)
                verify_snapshot()
                settings.chunk_size, settings.overlap = 200, 20
                verify_snapshot()
                documents.add_document_and_reindex("new.txt", "bread new note", chunk_size=200, overlap=20)
                verify_snapshot()
                documents.delete_document_and_reindex("a.md", chunk_size=200, overlap=20)
                verify_snapshot()
                documents.delete_document_and_reindex("new.txt", chunk_size=200, overlap=20)
                self.assertFalse(verify_snapshot().chunks)

    def test_fresh_indexes_follow_corpus_edits_and_keep_corpora_separate(self):
        with tempfile.TemporaryDirectory() as temp:
            baking = Path(temp) / "baking"
            kestrel = Path(temp) / "kestrel"
            baking.mkdir(); kestrel.mkdir()
            path = baking / "a.md"
            path.write_text("bread " * 30)
            (kestrel / "a.md").write_text("KST-2044 allowlist")
            with patch.dict(DATASET_DIRECTORIES, {"baking": baking, "kestrel": kestrel}):
                def search(dataset="baking", question="bread", size=100):
                    return retrieve_bm25(RetrievalQuery(question, dataset, 100, chunk_size=size, overlap=0)).chunks
                self.assertTrue(search())
                self.assertFalse(search("kestrel"))
                self.assertTrue(search("kestrel", "2044"))
                self.assertNotEqual(len(search(size=100)), len(search(size=200)))
                path.write_text("butter")
                self.assertFalse(search())
                (baking / "new.txt").write_text("bread")
                self.assertEqual(search()[0]["source"], "new.txt")
                (baking / "new.txt").unlink()
                self.assertFalse(search())

    def test_api_accepts_bm25_and_returns_existing_fused_contract(self):
        with patch("backend.bm25.load_documents", return_value=[doc("a.md", "bread flour")]):
            response = TestClient(app).post("/api/retrieve", json={
                "question": "bread", "retrievers": ["bm25"],
            })
        self.assertEqual(response.status_code, 200, response.text)
        chunk = FusedRetrievedChunk.model_validate(response.json()["chunks"][0])
        self.assertEqual(chunk.retrievers[0].score_type, "bm25")
        self.assertEqual(chunk.retrievers[0].rank, 1)


if __name__ == "__main__":
    unittest.main()
