
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

PLACEHOLDER_PATTERN = re.compile(
    r"\b(?:Person|Location|Entity)\s+[A-Z]\b"
)

EMAIL_PATTERN = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)

# Match common grouped phone formats without matching ordinary dates
# such as 2026-11-14 or short technical identifiers such as KST-2044.
PHONE_PATTERN = re.compile(
    r"(?<!\w)"
    r"(?!\d{4}[-/]\d{2}[-/]\d{2}\b)"
    r"(?:\+\d{1,3}[\s.-]?)?"
    r"(?:\(?\d{2,4}\)?[\s.-]){2,4}"
    r"\d{2,4}"
    r"(?!\w)"
)


def redact_personal_data(text: str) -> str:
    """
    Apply Presidio detection to text that may contain personal names
    and other personal information.
    """
    if not text:
        return text

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


def redact_contact_patterns(text: str) -> str:
    """
    Redact email addresses and common phone formats without
    applying person-name detection to document content.
    """
    if not text:
        return text

    text = EMAIL_PATTERN.sub("[REDACTED_EMAIL_ADDRESS]", text)
    text = PHONE_PATTERN.sub("[REDACTED_PHONE_NUMBER]", text)

    return text
