
import unittest

from backend.llm_service import build_prompt, build_style_instructions
from backend.schemas import AnswerStyle


class AnswerStyleTests(unittest.TestCase):
    def test_default_style(self):
        style = AnswerStyle()

        self.assertEqual(style.level, "beginner")
        self.assertEqual(style.tone, "friendly")
        self.assertEqual(style.length, "medium")
        self.assertFalse(style.eli12)

    def test_style_instructions_include_selected_options(self):
        style = AnswerStyle(
            level="expert",
            tone="technical",
            length="long",
            eli12=True,
        )

        instructions = build_style_instructions(style)

        self.assertIn("relevant domain knowledge", instructions)
        self.assertIn("technical tone", instructions)
        self.assertIn("detailed answer", instructions)
        self.assertIn("speaking to a 12-year-old", instructions)
        self.assertIn("citation requirements", instructions)

    def test_prompt_includes_style_instructions(self):
        style = AnswerStyle(
            level="beginner",
            tone="friendly",
            length="short",
            eli12=False,
        )

        chunks = [
            {
                "id": "chunk-1",
                "source": "guide.pdf",
                "position": 0,
                "text": "Sourdough fermentation uses yeast and bacteria.",
            }
        ]

        prompt = build_prompt(
            "What is sourdough fermentation?",
            chunks,
            style=style,
        )

        self.assertIn("Explain concepts clearly", prompt)
        self.assertIn("friendly, approachable tone", prompt)
        self.assertIn("Keep the answer brief", prompt)
        self.assertIn("sourdough fermentation", prompt)

    def test_default_prompt_still_works_without_style(self):
        chunks = [
            {
                "id": "chunk-1",
                "source": "guide.pdf",
                "position": 0,
                "text": "Example evidence.",
            }
        ]

        prompt = build_prompt("Test question", chunks)

        self.assertIn("ANSWER STYLE:", prompt)
        self.assertIn("friendly, approachable tone", prompt)


class AnswerStyleTraceTests(unittest.TestCase):
    def test_the_generation_span_records_the_style_used(self):
        from unittest.mock import MagicMock, patch
        from types import SimpleNamespace
        from backend import llm_service

        spans = []

        class Span:
            def __init__(self, name, attributes):
                self.name, self.attributes = name, dict(attributes or {})
            def __enter__(self):
                return self
            def __exit__(self, *exc):
                return False
            def set_attribute(self, key, value):
                self.attributes[key] = value

        class Trace:
            def span(self, name, *, attributes=None):
                spans.append(Span(name, attributes))
                return spans[-1]

        client = MagicMock()
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(
                content='{"status": "answered", "answer": "Chill it.", "cited_chunk_ids": ["c1"]}'
            ))],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        )
        chunk = {"id": "c1", "text": "Chill the dough.", "source": "a.md", "position": 0}
        style = AnswerStyle(level="expert", tone="technical", length="short", eli12=False)
        with patch.object(llm_service, "client", client):
            llm_service.generate_answer("How?", [chunk], trace=Trace(), style=style)

        generation = next(span for span in spans if span.name == "llm_generation")
        self.assertEqual(
            {k: generation.attributes[k] for k in ("style_level", "style_tone", "style_length", "style_eli12")},
            {"style_level": "expert", "style_tone": "technical", "style_length": "short", "style_eli12": False},
        )

if __name__ == "__main__":
    unittest.main()
