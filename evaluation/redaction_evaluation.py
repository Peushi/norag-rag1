import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.pii_redaction import redact_personal_data


DATASET_PATH = ROOT / "evaluation" / "redaction_cases_v4.json"
OUTPUT_PATH = (
    ROOT
    / "evaluation"
    / "results"
    / "v4"
    / "redaction_effectiveness_summary.json"
)


def contains(text: str, value: str) -> bool:
    return value.casefold() in text.casefold()


def evaluate_personal_cases(cases):
    total_targets = 0
    caught_targets = 0
    case_results = []

    for case in cases:
        question = case["question"]
        targets = case["expected_sensitive_values"]

        redacted = redact_personal_data(question)

        caught = 0

        for target in targets:
            if not contains(question, target):
                raise ValueError(
                    f"{case['id']}: labelled sensitive value is not in question"
                )

            total_targets += 1

            if not contains(redacted, target):
                caught += 1
                caught_targets += 1

        case_results.append({
            "id": case["id"],
            "targets": len(targets),
            "caught": caught,
            "all_targets_caught": caught == len(targets)
        })

    return {
        "questions": len(cases),
        "targets": total_targets,
        "caught": caught_targets,
        "missed": total_targets - caught_targets,
        "percentage": round(
            caught_targets / total_targets * 100, 1
        ) if total_targets else 0.0,
        "cases": case_results
    }


def evaluate_technical_cases(cases):
    total_terms = 0
    preserved_terms = 0
    case_results = []

    for case in cases:
        question = case["question"]
        terms = case["expected_technical_terms"]

        redacted = redact_personal_data(question)

        preserved = 0

        for term in terms:
            if not contains(question, term):
                raise ValueError(
                    f"{case['id']}: labelled technical term is not in question"
                )

            total_terms += 1

            if contains(redacted, term):
                preserved += 1
                preserved_terms += 1

        case_results.append({
            "id": case["id"],
            "terms": len(terms),
            "preserved": preserved,
            "all_terms_preserved": preserved == len(terms)
        })

    return {
        "questions": len(cases),
        "terms": total_terms,
        "preserved": preserved_terms,
        "removed_or_modified": total_terms - preserved_terms,
        "percentage": round(
            preserved_terms / total_terms * 100, 1
        ) if total_terms else 0.0,
        "cases": case_results
    }


def main():
    with DATASET_PATH.open("r", encoding="utf-8-sig") as file:
        dataset = json.load(file)

    personal_cases = dataset["personal_data_cases"]
    technical_cases = dataset["technical_term_cases"]

    if len(personal_cases) != 10 or len(technical_cases) != 10:
        raise ValueError("Expected exactly 10 cases in each evaluation group.")

    personal_results = evaluate_personal_cases(personal_cases)
    technical_results = evaluate_technical_cases(technical_cases)

    summary = {
        "evaluation": dataset["evaluation"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(DATASET_PATH.relative_to(ROOT)),
        "method": (
            "Each labelled target is checked against the output of "
            "redact_personal_data(). A target is caught if its original "
            "value is absent; a technical term is preserved if its original "
            "value remains present. Matching is case-insensitive."
        ),
        "personal_data_redaction": {
            key: value
            for key, value in personal_results.items()
        },
        "technical_term_preservation": {
            key: value
            for key, value in technical_results.items()
        },
        "limitations": [
            "This is a small labelled evaluation, not a comprehensive privacy guarantee.",
            "Results depend on the selected synthetic examples and recognizer configuration.",
            "A target being absent does not prove that every possible representation of that data was removed."
        ]
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, ensure_ascii=False)
        file.write("\n")

    print("\n=== V4 REDACTION EFFECTIVENESS ===")
    print(
        "Personal data caught: "
        f"{personal_results['caught']}/{personal_results['targets']} "
        f"({personal_results['percentage']}%)"
    )
    print(
        "Technical terms preserved: "
        f"{technical_results['preserved']}/{technical_results['terms']} "
        f"({technical_results['percentage']}%)"
    )
    print(f"\nSummary saved to: {OUTPUT_PATH.relative_to(ROOT)}")

    print("\n=== PERSONAL DATA CASES ===")
    for case in personal_results["cases"]:
        print(
            f"{case['id']}: {case['caught']}/{case['targets']} caught"
        )

    print("\n=== TECHNICAL TERM CASES ===")
    for case in technical_results["cases"]:
        print(
            f"{case['id']}: "
            f"{case['preserved']}/{case['terms']} preserved"
        )


if __name__ == "__main__":
    main()
