"""HTTP review workflow for quarantined uploads: list, release, reject.

Uses the same isolated corpora, quarantine folder, trace database and mocked
vector collection as the scanner/quarantine tests, so nothing real is touched.
"""

import unittest

# Import the module, not the class, so unittest does not collect its tests twice.
from tests import test_injection_quarantine as quarantine_setup

ATTACK = quarantine_setup.ATTACK


class QuarantineApiTests(unittest.TestCase):
    setUp = quarantine_setup.QuarantineTests.setUp
    trace = quarantine_setup.QuarantineTests.trace

    def upload_attack_via_api(self, name="attack.md"):
        response = self.client.post(
            "/api/documents",
            files={"file": (name, ATTACK, "text/markdown")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["status"], "quarantined")
        return body["quarantine_id"]

    def held_ids(self):
        response = self.client.get("/api/quarantine")
        self.assertEqual(response.status_code, 200, response.text)
        return [item["id"] for item in response.json()["items"]]

    def test_list_shows_findings_but_never_the_document_text(self):
        identifier = self.upload_attack_via_api()

        items = self.client.get("/api/quarantine").json()["items"]

        self.assertEqual([item["id"] for item in items], [identifier])
        item = items[0]
        self.assertEqual(item["source"], "attack.md")
        self.assertEqual(item["status"], "quarantined")
        self.assertTrue(item["findings"])
        self.assertEqual(
            set(item["findings"][0]),
            {"rule_id", "message", "severity", "line", "excerpt"},
        )
        self.assertNotIn("content", item)
        self.assertNotIn(ATTACK, str(items))

    def test_release_requires_explicit_approval(self):
        identifier = self.upload_attack_via_api()

        missing = self.client.post(f"/api/quarantine/{identifier}/release", json={})
        declined = self.client.post(
            f"/api/quarantine/{identifier}/release", json={"approved": False}
        )

        self.assertEqual(missing.status_code, 422)
        self.assertEqual(declined.status_code, 422)
        self.assertFalse((self.baking / "attack.md").exists())
        self.assertEqual(self.held_ids(), [identifier])

    def test_approved_release_indexes_once_and_is_traced(self):
        identifier = self.upload_attack_via_api()

        response = self.client.post(
            f"/api/quarantine/{identifier}/release", json={"approved": True}
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "indexed")
        self.assertEqual((self.baking / "attack.md").read_text(), ATTACK)
        self.assertEqual(self.held_ids(), [])
        trace = self.trace(response.headers["x-trace-id"])
        self.assertEqual(trace["operation"], "indexing")
        self.assertEqual(trace["outcome"], "indexed")
        self.assertIn("quarantine_release", [span["name"] for span in trace["spans"]])
        self.assertNotIn(ATTACK, str(trace))

        again = self.client.post(
            f"/api/quarantine/{identifier}/release", json={"approved": True}
        )
        self.assertEqual(again.status_code, 409)

    def test_reject_discards_the_document_and_is_traced(self):
        identifier = self.upload_attack_via_api()

        response = self.client.post(f"/api/quarantine/{identifier}/reject")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "rejected")
        self.assertFalse((self.baking / "attack.md").exists())
        self.assertEqual(self.held_ids(), [])
        trace = self.trace(response.headers["x-trace-id"])
        self.assertEqual(trace["operation"], "indexing")
        self.assertEqual(trace["outcome"], "rejected")

        release = self.client.post(
            f"/api/quarantine/{identifier}/release", json={"approved": True}
        )
        self.assertEqual(release.status_code, 409)

    def test_unknown_and_malformed_ids(self):
        unknown = "0" * 32
        self.assertEqual(
            self.client.post(f"/api/quarantine/{unknown}/reject").status_code, 404
        )
        self.assertEqual(
            self.client.post(
                f"/api/quarantine/{unknown}/release", json={"approved": True}
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post("/api/quarantine/not-an-id/reject").status_code, 422
        )

    def test_name_conflict_keeps_the_item_and_explains_what_to_do(self):
        identifier = self.upload_attack_via_api()
        (self.baking / "attack.md").write_text("A different document")

        response = self.client.post(
            f"/api/quarantine/{identifier}/release", json={"approved": True}
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("Remove it first", response.json()["error"]["message"])
        self.assertEqual((self.baking / "attack.md").read_text(), "A different document")
        self.assertEqual(self.held_ids(), [identifier])


if __name__ == "__main__":
    unittest.main()
