import json

from .documents import PROJECT_ROOT
from .retrieval import retrieve_chunks

QUESTIONS_PATH = PROJECT_ROOT / "evaluation" / "questions.json"


def evaluate_retrieval(top_k=5):
    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))

    total = 0
    hits = 0

    for item in questions:
        expected = set(item.get("expected_sources", []))

        # Exclude unanswerable questions from this hit-rate metric.
        if not expected:
            print(f"{item['id']}: UNANSWERABLE | Excluded from Hit@{top_k}")
            continue

        total += 1

        chunks = retrieve_chunks(
            question=item["question"],
            top_k=top_k,
        )

        found_sources = {chunk["source"] for chunk in chunks}
        hit = bool(expected & found_sources)

        if hit:
            hits += 1

        print(
            f"{item['id']}: "
            f"{'HIT' if hit else 'MISS'} | "
            f"Retrieved: {sorted(found_sources)}"
        )

    hit_rate = hits / total if total else 0.0

    print(f"\nHit@{top_k}: {hits}/{total} = {hit_rate:.1%}")

    return hit_rate


if __name__ == "__main__":
    evaluate_retrieval()
