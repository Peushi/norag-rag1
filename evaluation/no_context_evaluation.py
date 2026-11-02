import argparse
import json
from pathlib import Path

from backend.llm_service import MODEL, client


def load_questions(path: Path) -> list[dict]:
    questions = []

    with path.open("r", encoding="utf-8-sig") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                questions.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on line {line_number} of {path}"
                ) from exc

    return questions


def ask_without_context(question: str) -> str:
    """Ask Gemini a question without providing any retrieved documents."""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant. Answer the user's question "
                    "using your general knowledge only. You do not have access "
                    "to any knowledge base, documents, or external retrieval. "
                    "If you do not know the answer, say so. Do not invent facts."
                ),
            },
            {
                "role": "user",
                "content": question,
            },
        ],
    )

    answer = response.choices[0].message.content

    if not answer:
        raise ValueError("Gemini returned an empty answer.")

    return answer.strip()


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate Gemini without retrieval or document context."
    )
    parser.add_argument("--input", required=True, help="Input questions JSONL")
    parser.add_argument("--output", required=True, help="Output results JSONL")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional number of questions to test",
    )

    args = parser.parse_args()

    if client is None:
        raise RuntimeError(
            "GOOGLE_API_KEY is missing. Check your local .env file."
        )

    input_path = Path(args.input)
    output_path = Path(args.output)

    questions = load_questions(input_path)

    if args.limit is not None:
        questions = questions[:args.limit]

    if not questions:
        raise ValueError("No questions found in the input file.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Model: {MODEL}")
    print(f"Input: {input_path}")
    print(f"Questions to evaluate: {len(questions)}")
    print()

    with output_path.open("w", encoding="utf-8") as output_file:
        for index, item in enumerate(questions, start=1):
            question_id = item["id"]
            question = item["question"]

            print(f"[{index}/{len(questions)}] Testing {question_id}...")

            result = {
                "id": question_id,
                "question": question,
                "type": item.get("type", "other"),
                "answerable": item.get("answerable"),
                "expected_answer": item.get("expected_answer", ""),
                "model": MODEL,
                "model_answer": None,
                "correct_without_context": None,
                "manual_review": "pending",
                "error": None,
            }

            try:
                result["model_answer"] = ask_without_context(question)
                print("  Answer received.")
            except Exception as exc:
                result["error"] = str(exc)
                print(f"  ERROR: {exc}")

            output_file.write(
                json.dumps(result, ensure_ascii=False) + "\n"
            )
            output_file.flush()

    print()
    print("Evaluation finished.")
    print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    main()
