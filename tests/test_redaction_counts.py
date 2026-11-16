"""Redaction records what it removed (counts and types), never the values."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend import llm_service
from backend.metrics import compute_metrics
from backend.pii_redaction import count_redactions, describe_redactions


class CountTests(unittest.TestCase):
    def test_counts_only_placeholders_added_by_redaction(self):
        before = "Ask [REDACTED_PERSON] or Jane at jane@example.com"
        after = "Ask [REDACTED_PERSON] or [REDACTED_PERSON] at [REDACTED_EMAIL_ADDRESS]"

        counts = count_redactions(before, after)

        self.assertEqual(counts, {"PERSON": 1, "EMAIL_ADDRESS": 1})
        self.assertEqual(describe_redactions(counts), "EMAIL_ADDRESS:1, PERSON:1")
        self.assertEqual(count_redactions("nothing here", "nothing here"), {})


class Span:
    def __init__(self, name, attributes):
        self.name, self.attributes = name, dict(attributes or {})

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def set_attribute(self, key, value):
        from backend.tracing import _validate_attribute

        _validate_attribute(key, value)  # the real trace store's rules
        self.attributes[key] = value


class Trace:
    def __init__(self):
        self.spans = []

    def span(self, name, *, attributes=None):
        self.spans.append(Span(name, attributes))
        return self.spans[-1]


class RedactionSpanTests(unittest.TestCase):
    def test_the_trace_shows_how_much_was_removed_but_not_what(self):
        chunk = {"id": "c1", "text": "Call the bakery on +33 6 12 34 56 78 for orders.", "source": "a.md", "position": 0}
        client = MagicMock()
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(
                content='{"status": "answered", "answer": "Call the bakery.", "cited_chunk_ids": ["c1"]}'
            ))],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        )
        trace = Trace()
        with patch.object(llm_service, "client", client):
            llm_service.generate_answer(
                "I am Jane Doe, jane.doe@example.com. How do I order?", [chunk], trace=trace
            )

        redaction = next(s for s in trace.spans if s.name == "pii_redaction")
        attributes = redaction.attributes
        self.assertGreaterEqual(attributes["user_text_redactions"], 2)
        self.assertIn("EMAIL_ADDRESS", attributes["user_text_redaction_types"])
        self.assertIn("PERSON", attributes["user_text_redaction_types"])
        self.assertEqual(attributes["pattern_redactions"], 1)
        self.assertEqual(attributes["pattern_redaction_types"], "PHONE_NUMBER:1")
        stored = json.dumps(attributes)
        for value in ("Jane", "jane.doe@example.com", "12 34 56"):
            self.assertNotIn(value, stored)

    def test_nothing_to_remove_records_zeros(self):
        chunk = {"id": "c1", "text": "Chill the dough.", "source": "a.md", "position": 0}
        client = MagicMock()
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(
                content='{"status": "answered", "answer": "Chill it.", "cited_chunk_ids": ["c1"]}'
            ))],
            usage=None,
        )
        trace = Trace()
        with patch.object(llm_service, "client", client):
            llm_service.generate_answer("How do I stop cookies spreading?", [chunk], trace=trace)

        attributes = next(s for s in trace.spans if s.name == "pii_redaction").attributes
        self.assertEqual((attributes["user_text_redactions"], attributes["pattern_redactions"]), (0, 0))
        self.assertNotIn("user_text_redaction_types", attributes)


class PrivacyMetricsTests(unittest.TestCase):
    def test_metrics_add_up_redactions_across_questions(self):
        def question(**redaction):
            return {
                "operation": "question", "status": "completed", "outcome": "answered",
                "started_at": "2026-11-16T10:00:00+00:00", "completed_at": "2026-11-16T10:00:01+00:00",
                "spans": [{"name": "pii_redaction", "status": "completed", "duration_ms": 5, "attributes": redaction}],
            }

        traces = [
            question(user_text_redactions=2, pattern_redactions=1,
                     user_text_redaction_types="EMAIL_ADDRESS:1, PERSON:1", pattern_redaction_types="PHONE_NUMBER:1"),
            question(user_text_redactions=0, pattern_redactions=0),
            question(),  # recorded before counts existed: not counted as checked
        ]
        privacy = compute_metrics(traces, 7)["privacy"]

        self.assertEqual(privacy["questions_checked"], 2)
        self.assertEqual(privacy["questions_with_personal_data"], 1)
        self.assertEqual(privacy["items_removed"], 3)
        self.assertEqual(privacy["by_type"], {"EMAIL_ADDRESS": 1, "PERSON": 1, "PHONE_NUMBER": 1})


if __name__ == "__main__":
    unittest.main()
