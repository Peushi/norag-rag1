import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend import llm_service


class FakeSpan:
    def __init__(self, name, attributes=None):
        self.name = name
        self.attributes = dict(attributes or {})
        self.exception = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.exception = exc_type
        return False

    def set_attribute(self, key, value):
        self.attributes[key] = value


class FakeTrace:
    def __init__(self):
        self.trace_id = "test-trace-123"
        self.spans = []

    def span(self, name, *, attributes=None):
        span = FakeSpan(name, attributes)
        self.spans.append(span)
        return span


def make_response(content, usage=True):
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content)
            )
        ]
    )

    if usage:
        response.usage = SimpleNamespace(
            prompt_tokens=120,
            completion_tokens=35,
        )

    return response


class LLMTracingTests(unittest.TestCase):

    def setUp(self):
        self.chunk = {
            "id": "chunk-1",
            "text": "The recipe requires 200 grams of flour.",
            "source": "recipe.pdf",
            "position": 0,
        }

        self.valid_response = (
            '{"status": "answered", '
            '"answer": "Use 200 grams of flour.", '
            '"cited_chunk_ids": ["chunk-1"]}'
        )

    def mock_client(self, content=None, usage=True):
        response = make_response(
            content or self.valid_response,
            usage=usage,
        )

        client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=unittest.mock.Mock(return_value=response)
                )
            )
        )

        return client

    def test_all_four_spans_are_created(self):
        trace = FakeTrace()
        client = self.mock_client()

        with patch.object(llm_service, "client", client):
            result = llm_service.generate_answer(
                "How much flour is required?",
                [self.chunk],
                trace=trace,
            )

        self.assertEqual(result.status, "answered")
        self.assertEqual(
            [span.name for span in trace.spans],
            [
                "pii_redaction",
                "llm_generation",
                "response_validation",
                "citation_verification",
            ],
        )

    def test_generation_records_token_counts(self):
        trace = FakeTrace()
        client = self.mock_client()

        with patch.object(llm_service, "client", client):
            llm_service.generate_answer(
                "How much flour is required?",
                [self.chunk],
                trace=trace,
            )

        generation_span = next(
            span for span in trace.spans
            if span.name == "llm_generation"
        )

        self.assertEqual(
            generation_span.attributes["input_tokens"],
            120,
        )
        self.assertEqual(
            generation_span.attributes["output_tokens"],
            35,
        )
        self.assertEqual(
            generation_span.attributes["model"],
            llm_service.MODEL,
        )

    def test_personal_data_is_redacted_before_gemini(self):
        trace = FakeTrace()

        private_chunk = {
            "id": "chunk-1",
            "text": "Contact John Smith at john@example.com.",
            "source": "private.pdf",
            "position": 0,
        }

        client = self.mock_client()

        def fake_redaction(prompt):
            return (
                prompt
                .replace("John Smith", "[REDACTED_PERSON]")
                .replace(
                    "john@example.com",
                    "[REDACTED_EMAIL_ADDRESS]",
                )
            )

        with (
            patch.object(llm_service, "client", client),
            patch.object(
                llm_service,
                "redact_personal_data",
                side_effect=fake_redaction,
            ),
        ):
            llm_service.generate_answer(
                "Who should I contact?",
                [private_chunk],
                trace=trace,
            )

        sent_prompt = (
            client.chat.completions.create.call_args.kwargs[
                "messages"
            ][1]["content"]
        )

        self.assertNotIn("John Smith", sent_prompt)
        self.assertNotIn("john@example.com", sent_prompt)
        self.assertIn("[REDACTED_PERSON]", sent_prompt)
        self.assertIn("[REDACTED_EMAIL_ADDRESS]", sent_prompt)

    def test_validation_failure_marks_span_as_failed(self):
        trace = FakeTrace()
        client = self.mock_client(content="This is not JSON")

        with (
            patch.object(llm_service, "client", client),
            self.assertRaises(llm_service.LLMResponseError),
        ):
            llm_service.generate_answer(
                "How much flour is required?",
                [self.chunk],
                trace=trace,
            )

        validation_span = next(
            span for span in trace.spans
            if span.name == "response_validation"
        )

        self.assertIsNotNone(validation_span.exception)

    def test_invalid_citation_marks_verification_span_as_failed(self):
        trace = FakeTrace()

        invalid_response = (
            '{"status": "answered", '
            '"answer": "Use 200 grams of flour.", '
            '"cited_chunk_ids": ["invented-chunk"]}'
        )

        client = self.mock_client(content=invalid_response)

        with (
            patch.object(llm_service, "client", client),
            self.assertRaises(llm_service.LLMResponseError),
        ):
            llm_service.generate_answer(
                "How much flour is required?",
                [self.chunk],
                trace=trace,
            )

        citation_span = next(
            span for span in trace.spans
            if span.name == "citation_verification"
        )

        self.assertIsNotNone(citation_span.exception)

    def test_trace_attributes_do_not_contain_prompt_or_document_text(self):
        trace = FakeTrace()
        client = self.mock_client()

        with patch.object(llm_service, "client", client):
            llm_service.generate_answer(
                "How much flour is required?",
                [self.chunk],
                trace=trace,
            )

        sensitive_values = [
            "How much flour is required?",
            "The recipe requires 200 grams of flour.",
            "recipe.pdf",
        ]

        for span in trace.spans:
            for value in span.attributes.values():
                if isinstance(value, str):
                    for sensitive_value in sensitive_values:
                        self.assertNotIn(sensitive_value, value)


if __name__ == "__main__":
    unittest.main()
