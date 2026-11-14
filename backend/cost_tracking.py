
"""Shared estimated LLM token-cost calculations."""

from typing import Final


# Standard paid-tier prices in USD per 1 million tokens.
# Source: https://ai.google.dev/gemini-api/docs/pricing
MODEL_PRICING_USD_PER_MILLION: Final = {
    "gemini-3.5-flash-lite": {
        "input": 0.30,
        "output": 2.50,
    },
}


def calculate_cost_usd(
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
) -> float | None:
    """Estimate model cost from input/output token usage.

    Returns None when usage is unavailable or the model has no
    configured pricing.
    """
    if input_tokens is None or output_tokens is None:
        return None

    if (
        isinstance(input_tokens, bool)
        or isinstance(output_tokens, bool)
        or not isinstance(input_tokens, int)
        or not isinstance(output_tokens, int)
        or input_tokens < 0
        or output_tokens < 0
    ):
        raise ValueError("Token counts must be non-negative integers.")

    pricing = MODEL_PRICING_USD_PER_MILLION.get(model)

    if pricing is None:
        return None

    input_cost = input_tokens * pricing["input"] / 1_000_000
    output_cost = output_tokens * pricing["output"] / 1_000_000

    return input_cost + output_cost
