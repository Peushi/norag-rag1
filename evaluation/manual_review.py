import argparse
import json
from pathlib import Path


EVALUATION_DIR = Path(__file__).resolve().parent


BAKING_REVIEWS = {
    "B01": {"grade": "correct", "type": "answer", "reason": "Correctly identifies the hot baking sheet from the previous batch as the cause."},
    "B02": {"grade": "correct", "type": "answer", "reason": "Accurately gives the recommended dough temperature, proofing environment, and ways to warm a cold kitchen."},
    "B03": {"grade": "correct", "type": "answer", "reason": "Correctly explains the ingredient balance that produces fudgy brownies."},
    "B04": {"grade": "correct", "type": "answer", "reason": "Correctly describes the fluff, sprinkle, and scrape method for measuring flour."},
    "B05": {"grade": "correct", "type": "answer", "reason": "Gives the correct weekly refrigeration feeding routine and quantities."},
    "B06": {"grade": "correct", "type": "answer", "reason": "Provides suitable ways to reuse soggy pie crust and its crumbs, supported by the retrieved documents."},
    "B07": {"grade": "correct", "type": "answer", "reason": "Correctly describes chilling, using sufficient pie weights, and the two-pan method."},
    "B08": {"grade": "correct", "type": "answer", "reason": "Gives an appropriate feeding routine for reviving a neglected starter, supported by the source."},
    "B09": {"grade": "correct", "type": "answer", "reason": "Identifies the documented causes of dense banana bread."},
    "B10": {"grade": "correct", "type": "answer", "reason": "Correctly explains how excess flour can make cookies dry or crumbly and how to measure flour accurately."},
    "B11": {"grade": "correct", "type": "refusal", "reason": "Correctly refuses because the baking documents do not contain the requested pasta information."},
    "B12": {"grade": "correct", "type": "refusal", "reason": "Correctly refuses the unrelated bicycle question because it is outside the available knowledge base."},
}


KESTREL_REVIEWS = {
    "q01": {
        "grade": "wrong",
        "type": "answer",
        "reason": "The runbook explicitly explains KST-2044: the customer must allowlist both 203.0.113.10 and 203.0.113.11. The model incorrectly returned not_found."
    },
    "q02": {
        "grade": "correct",
        "type": "answer",
        "reason": "Correctly explains that an Admin can remove a member or the Owner can add seats or upgrade the plan, and that the invitation remains valid for less than 7 days."
    },
    "q03": {
        "grade": "correct",
        "type": "answer",
        "reason": "Correctly describes the payment notification, automatic retries, 21-day grace period, read-only state, and suspension after 60 days."
    },
    "q04": {
        "grade": "correct",
        "type": "answer",
        "reason": "Correctly identifies Business and Enterprise SSO availability and the documented SAML setup steps."
    },
    "q05": {
        "grade": "correct",
        "type": "answer",
        "reason": "Correctly explains backup-code recovery, Admin second-factor reset, and the support process for the only Admin or Owner."
    },
    "q06": {
        "grade": "correct",
        "type": "answer",
        "reason": "Correctly applies the 2026 annual refund policy: requests within 60 days can receive a refund for unused full months."
    },
    "q07": {
        "grade": "wrong",
        "type": "answer",
        "reason": "The 2026 billing policy explicitly states that annual billing gives a 20% discount compared with twelve months of monthly billing. The model incorrectly returned not_found."
    },
    "q08": {
        "grade": "partial",
        "type": "answer",
        "reason": "Correctly identifies postroom and SEV-2 escalation, but fails to name its owning team, Messaging, and its on-call channel, #oncall-messaging."
    },
    "q09": {
        "grade": "correct",
        "type": "refusal",
        "reason": "Correctly refuses because the knowledge base does not establish whether a Kestrel iPhone app exists."
    },
    "q10": {
        "grade": "correct",
        "type": "refusal",
        "reason": "Correctly refuses to invent a Business seat price. The billing policy states that current prices are published separately and are not repeated in the document."
    },
}


REVIEWS = {
    "baking": BAKING_REVIEWS,
    "kestrel": KESTREL_REVIEWS,
}


def main():
    parser = argparse.ArgumentParser(
        description="Apply manual grades to RAG evaluation results."
    )
    parser.add_argument(
        "--dataset",
        choices=["baking", "kestrel"],
        required=True,
    )
    args = parser.parse_args()

    input_path = EVALUATION_DIR / "results" / f"{args.dataset}_rag.jsonl"
    output_path = EVALUATION_DIR / "results" / f"{args.dataset}_rag_reviewed.jsonl"

    reviews = REVIEWS[args.dataset]

    with input_path.open("r", encoding="utf-8") as file:
        results = [json.loads(line) for line in file if line.strip()]

    found_ids = {result["id"] for result in results}
    missing_ids = set(reviews) - found_ids

    if missing_ids:
        raise RuntimeError(
            f"Missing evaluation results for: {sorted(missing_ids)}"
        )

    with output_path.open("w", encoding="utf-8") as file:
        for result in results:
            result["manual_review"] = reviews[result["id"]]
            file.write(json.dumps(result, ensure_ascii=False) + "\n")

    grades = [review["grade"] for review in reviews.values()]

    print(f"Reviewed results saved to: {output_path}")
    print(f"Questions graded: {len(reviews)}")
    print(f"Correct: {grades.count('correct')}")
    print(f"Partial: {grades.count('partial')}")
    print(f"Wrong: {grades.count('wrong')}")


if __name__ == "__main__":
    main()
