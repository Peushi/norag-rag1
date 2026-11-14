
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


if __name__ == "__main__":
    unittest.main()
