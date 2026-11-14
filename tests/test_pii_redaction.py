import unittest

from backend.pii_redaction import (
    redact_contact_patterns,
    redact_personal_data,
)


class PIIRedactionTests(unittest.TestCase):

    # Full Presidio redaction tests

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

    # Conservative contact-pattern redaction tests

    def test_contact_patterns_redact_email(self):
        text = "Contact support at help@example.com."
        result = redact_contact_patterns(text)

        self.assertIn("[REDACTED_EMAIL_ADDRESS]", result)
        self.assertNotIn("help@example.com", result)

    def test_contact_patterns_redact_phone_number(self):
        text = "Call +1 415-555-0132 for assistance."
        result = redact_contact_patterns(text)

        self.assertIn("[REDACTED_PHONE_NUMBER]", result)
        self.assertNotIn("+1 415-555-0132", result)

    def test_contact_patterns_preserve_product_names(self):
        text = "Vellora is supported by the service."
        self.assertEqual(redact_contact_patterns(text), text)

    def test_contact_patterns_preserve_technical_identifiers(self):
        text = "Investigate KST-2044 using error code ERR-500."
        self.assertEqual(redact_contact_patterns(text), text)

    def test_contact_patterns_preserve_dates(self):
        text = "The policy takes effect on 2026-11-14."
        self.assertEqual(redact_contact_patterns(text), text)

    def test_contact_patterns_preserve_generic_graph_labels(self):
        text = "Person A is connected to Entity B."
        self.assertEqual(redact_contact_patterns(text), text)

    def test_contact_patterns_returns_empty_text_unchanged(self):
        self.assertEqual(redact_contact_patterns(""), "")

    def test_contact_patterns_does_not_modify_original_input(self):
        text = "Contact help@example.com."
        original = text

        redact_contact_patterns(text)

        self.assertEqual(text, original)


if __name__ == "__main__":
    unittest.main()
