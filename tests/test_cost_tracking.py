
import unittest

from backend.cost_tracking import calculate_cost_usd


class CostTrackingTests(unittest.TestCase):
    def test_calculates_input_and_output_cost(self):
        cost = calculate_cost_usd(
            "gemini-3.5-flash-lite",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )

        self.assertAlmostEqual(cost, 2.80)

    def test_calculates_small_token_usage(self):
        cost = calculate_cost_usd(
            "gemini-3.5-flash-lite",
            input_tokens=10_000,
            output_tokens=2_000,
        )

        expected = (10_000 * 0.30 + 2_000 * 2.50) / 1_000_000
        self.assertAlmostEqual(cost, expected)

    def test_returns_none_when_input_usage_is_missing(self):
        self.assertIsNone(
            calculate_cost_usd("gemini-3.5-flash-lite", None, 100)
        )

    def test_returns_none_when_output_usage_is_missing(self):
        self.assertIsNone(
            calculate_cost_usd("gemini-3.5-flash-lite", 100, None)
        )

    def test_returns_none_for_unknown_model(self):
        self.assertIsNone(
            calculate_cost_usd("unknown-model", 100, 100)
        )

    def test_rejects_negative_token_counts(self):
        with self.assertRaises(ValueError):
            calculate_cost_usd("gemini-3.5-flash-lite", -1, 100)

    def test_rejects_non_integer_token_counts(self):
        with self.assertRaises(ValueError):
            calculate_cost_usd("gemini-3.5-flash-lite", 1.5, 100)


if __name__ == "__main__":
    unittest.main()
