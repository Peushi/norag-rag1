import unittest

from backend.pii_redaction import redact_personal_data


class PIIRedactionTests(unittest.TestCase):

    def test_redacts_person_name(self):
        result = redact_personal_data("John Smith visited the office.")
        self.assertIn("[REDACTED_PERSON]", result)
        self.assertNotIn("John Smith", result)

    def test_redacts_email(self):
        result = redact_personal_data("Contact john.smith@example.com.")
        self.assertIn("[REDACTED_EMAIL_ADDRESS]", result)
        self.assertNotIn("john.smith@example.com", result)

    def test_redacts_phone_number(self):
        result = redact_personal_data("Call +1 415-555-0132.")
        self.assertIn("[REDACTED_PHONE_NUMBER]", result)
        self.assertNotIn("+1 415-555-0132", result)

    def test_preserves_generic_graph_labels(self):
        text = "Person A visited Location B."
        self.assertEqual(redact_personal_data(text), text)

    def test_preserves_ordinary_locations(self):
        text = "John Smith visited Paris."
        result = redact_personal_data(text)
        self.assertIn("Paris", result)

    def test_returns_empty_text_unchanged(self):
        self.assertEqual(redact_personal_data(""), "")

    def test_does_not_modify_original_input(self):
        text = "Contact john.smith@example.com."
        original = text
        redact_personal_data(text)
        self.assertEqual(text, original)


if __name__ == "__main__":
    unittest.main()
