import unittest

from backend.graph_retrieval import retrieve_graph


class TestGraphRetrieval(unittest.TestCase):

    def test_postroom_owner(self):
        result = retrieve_graph("Who owns postroom?")

        self.assertTrue(any(
            edge["subject"]["name"] == "postroom"
            and edge["relation"] == "OWNED_BY"
            and edge["object"]["name"] == "Messaging"
            for path in result["paths"]
            for edge in path["edges"]
        ))

        self.assertTrue(any(
            chunk["source"] == "service-catalog.md"
            for chunk in result["chunks"]
        ))

    def test_kst_6010_escalation(self):
        result = retrieve_graph("Who handles KST-6010?")

        self.assertTrue(any(
            edge["subject"]["name"] == "KST-6010"
            and edge["relation"] == "ESCALATES_TO"
            and edge["object"]["name"] == "Payments Core"
            for path in result["paths"]
            for edge in path["edges"]
        ))

    def test_policy_replacement(self):
        result = retrieve_graph(
            "What replaced Billing and Refund Policy 2025?"
        )

        self.assertEqual(
            result["matched_entities"][0]["name"],
            "Billing and Refund Policy 2025",
        )

        self.assertTrue(any(
            edge["subject"]["name"] == "Billing and Refund Policy 2026"
            and edge["relation"] == "REPLACES"
            and edge["object"]["name"] == "Billing and Refund Policy 2025"
            for path in result["paths"]
            for edge in path["edges"]
        ))


if __name__ == "__main__":
    unittest.main()
