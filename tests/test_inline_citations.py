"""Passage IDs the model writes into the answer become source numbers."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend import llm_service
from backend.llm_service import number_inline_citations

A, B, C = "61137270eed8::chunk_0000", "61137270eed8::chunk_0005", "aaaaaaaaaaaa::chunk_0002"


class NumberInlineCitationsTests(unittest.TestCase):
    def test_the_reported_answer_gets_numbers_instead_of_ids(self):
        answer = (
            "Yeast bread may fail to rise ... or the dough containing too much sugar "
            f"[{A}]. Excess sugar binds available water [{B}]."
        )

        text, replaced = number_inline_citations(answer, [A, B], {A, B})

        self.assertEqual(
            text,
            "Yeast bread may fail to rise ... or the dough containing too much sugar [1]. "
            "Excess sugar binds available water [2].",
        )
        self.assertEqual(replaced, 2)

    def test_several_ids_in_one_bracket_and_parentheses(self):
        text, _ = number_inline_citations(f"Chill it [{B}, {A}] and wait ({A}).", [A, B], {A, B})

        self.assertEqual(text, "Chill it [1, 2] and wait [1].")

    def test_a_retrieved_but_uncited_id_is_removed(self):
        text, replaced = number_inline_citations(f"Chill it [{C}].", [A], {A, C})

        self.assertEqual(text, "Chill it.")
        self.assertEqual(replaced, 1)

    def test_other_brackets_are_left_alone(self):
        answer = "See [the guide](https://example.com) (about 20 minutes) [note] [2]."

        text, replaced = number_inline_citations(answer, [A], {A})

        self.assertEqual(text, answer)
        self.assertEqual(replaced, 0)

    def test_an_unknown_id_is_not_rewritten(self):
        answer = "Chill it [zzzzzzzzzzzz::chunk_0009]."
        self.assertEqual(number_inline_citations(answer, [A], {A}), (answer, 0))


class GeneratedAnswerTests(unittest.TestCase):
    def test_generated_answers_never_show_passage_ids(self):
        chunks = [
            {"id": A, "text": "Too much sugar slows rising.", "source": "bread.md", "position": 0},
            {"id": B, "text": "Sugar binds water.", "source": "bread.md", "position": 5},
        ]
        content = json.dumps({
            "status": "answered",
            "answer": f"Too much sugar slows rising [{A}]; it binds water [{B}].",
            "cited_chunk_ids": [A, B],
        })
        client = MagicMock()
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))], usage=None
        )
        with patch.object(llm_service, "client", client):
            result = llm_service.generate_answer("Why didn't my bread rise?", chunks)

        self.assertEqual(result.answer, "Too much sugar slows rising [1]; it binds water [2].")
        self.assertEqual([r.chunk_id for r in result.references], [A, B])
        prompt = client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        self.assertIn("never in the answer text", prompt)


if __name__ == "__main__":
    unittest.main()
