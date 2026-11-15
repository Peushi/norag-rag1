"""The AI-BOM (aibom/bakefix.cdx.json) must describe the code as it is.

Fails when a model revision, the lock files, or a bundled dataset changes
without regenerating the BOM: python scripts/generate_aibom.py
"""

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("generate_aibom", ROOT / "scripts" / "generate_aibom.py")
generate_aibom = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate_aibom)


class AiBomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = generate_aibom.OUTPUT_FILE.read_text()
        cls.bom = json.loads(cls.text)

    def component(self, ref):
        return next(c for c in self.bom["components"] if c["bom-ref"] == ref)

    def test_committed_bom_matches_the_code_lock_files_and_datasets(self):
        self.assertEqual(
            generate_aibom.render(generate_aibom.build_bom()),
            self.text,
            "aibom/bakefix.cdx.json is out of date: run python scripts/generate_aibom.py",
        )

    def test_the_embedding_model_loaded_by_the_app_is_the_one_in_the_bom(self):
        from backend import vector_store

        model = self.component("model:all-MiniLM-L6-v2")
        self.assertEqual(vector_store.EMBEDDING_MODEL, model["name"])
        self.assertEqual(vector_store.EMBEDDING_MODEL_REVISION, model["version"])
        # The revision is actually passed to the model loader, not just declared.
        self.assertEqual(
            vector_store._embedding_fn.kwargs.get("revision"), vector_store.EMBEDDING_MODEL_REVISION
        )

    def test_cached_weights_match_the_bom_hash(self):
        problem = generate_aibom.check_cached_weights(self.bom)
        self.assertIsNone(problem, problem)

    def test_every_ai_component_has_a_licence_hash_and_model_card(self):
        models = [c for c in self.bom["components"] if c["type"] == "machine-learning-model"]
        local = [m for m in models if m["bom-ref"] != "model:gemini"]
        self.assertEqual({m["name"] for m in local}, {"all-MiniLM-L6-v2", "en_core_web_sm"})
        # Local models are pinned and licensed; Gemini is hosted and pinned by name only.
        for model in local:
            self.assertTrue(model["licenses"], model["name"])
            self.assertTrue(model["hashes"], model["name"])
        # Every model card states limits and at least one measured result.
        for model in models:
            card = model["modelCard"]
            self.assertTrue(card["considerations"]["technicalLimitations"], model["name"])
            self.assertTrue(card["quantitativeAnalysis"]["performanceMetrics"], model["name"])
        for data in (c for c in self.bom["components"] if c["type"] == "data"):
            self.assertTrue(data["hashes"], data["name"])

    def test_the_external_llm_declares_what_data_it_receives(self):
        (gemini,) = self.bom["services"]
        self.assertTrue(gemini["x-trust-boundary"])
        outbound = [d for d in gemini["data"] if d["flow"] == "outbound"]
        self.assertIn("redaction", outbound[0]["description"])

    def test_bom_is_valid_cyclonedx_1_6(self):
        try:
            import cyclonedx  # noqa: F401
        except ImportError:
            self.skipTest("pip install -r requirements-dev.txt to validate the schema")
        self.assertEqual(generate_aibom.validate(self.text), [])

    def test_every_known_vulnerability_has_a_decision_about_a_component_we_ship(self):
        vex = json.loads((ROOT / "aibom" / "bakefix.vex.cdx.json").read_text())
        refs = {c["bom-ref"] for c in self.bom["components"]}
        for vulnerability in vex["vulnerabilities"]:
            state = vulnerability["analysis"]["state"]
            self.assertNotIn(state, {"in_triage", "exploitable"}, vulnerability["id"])
            self.assertTrue(vulnerability["analysis"].get("detail"), vulnerability["id"])
            for affected in vulnerability["affects"]:
                self.assertIn(affected["ref"].split("#", 1)[1], refs, vulnerability["id"])
        try:
            import cyclonedx  # noqa: F401
        except ImportError:
            return
        self.assertEqual(generate_aibom.validate(json.dumps(vex)), [])


if __name__ == "__main__":
    unittest.main()
