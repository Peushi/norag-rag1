"""Local personal information detection and redaction using Presidio."""

import re
from functools import lru_cache

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider


NLP_CONFIGURATION = {
    "nlp_engine_name": "spacy",
    "models": [
        {
            "lang_code": "en",
            "model_name": "en_core_web_sm",
        }
    ],
}


@lru_cache(maxsize=1)
def get_analyzer() -> AnalyzerEngine:
    """Create and reuse a local Presidio analyzer."""
    provider = NlpEngineProvider(nlp_configuration=NLP_CONFIGURATION)
    nlp_engine = provider.create_engine()

    return AnalyzerEngine(
        nlp_engine=nlp_engine,
        supported_languages=["en"],
    )


PERSONAL_ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "IP_ADDRESS",
    "CREDIT_CARD",
    "IBAN_CODE",
    "US_SSN",
]

# Preserve generic labels commonly used in graph fixtures and documentation.
PLACEHOLDER_PATTERN = re.compile(
    r"\b(?:Person|Location|Entity)\s+[A-Z]\b"
)


def redact_personal_data(text: str) -> str:
    """
    Detect and replace personal information locally.

    Generic entity labels are protected from false-positive detection.
    The original input is never modified.
    """
    if not text:
        return text

    # Mask placeholders with spaces so Presidio cannot classify them.
    # Keeping the same length preserves all detection character offsets.
    analysis_text = PLACEHOLDER_PATTERN.sub(
        lambda match: " " * len(match.group()),
        text,
    )

    results = get_analyzer().analyze(
        text=analysis_text,
        language="en",
        entities=PERSONAL_ENTITIES,
    )

    results = sorted(
        results,
        key=lambda result: (result.start, result.end),
        reverse=True,
    )

    redacted_text = text
    last_start = len(text) + 1

    for result in results:
        if result.end > last_start:
            continue

        replacement = f"[REDACTED_{result.entity_type}]"
        redacted_text = (
            redacted_text[:result.start]
            + replacement
            + redacted_text[result.end:]
        )
        last_start = result.start

    return redacted_text
