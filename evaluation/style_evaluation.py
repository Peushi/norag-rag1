"""Answer style controls: do they work, and what do they cost? (V4, Part B)

Runs the same questions in several styles through the real pipeline (retrieval,
redaction, generation, citation checks) and measures each answer:

- length in words, and readability (Flesch reading ease: higher = easier);
- whether it is answered or refused, with how many validated citations;
- glossary entries, tokens, cost and latency (from the answer's own trace).

Checks, per question:
- length controls order the answers: short < medium < long (same level and tone);
- "Explain it like I'm 12" reads easier than "expert, technical";
- a question the documents do not cover is refused in every style;
- every answered response keeps valid citations (otherwise it is rejected).

    python -m evaluation.style_evaluation        # needs a configured LLM; 25 calls

Writes evaluation/results/v4/answer_style_eval.json. Questions and documents
are the public evaluation corpora; no user data is involved.
"""

from __future__ import annotations

import json
import re
import statistics
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from openai import APIStatusError, RateLimitError

from backend.llm_service import MODEL, LLMResponseError
from backend.rag_service import ask_question
from backend.schemas import AnswerStyle
from backend.tracing import create_trace, get_trace

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "evaluation" / "results" / "v4" / "answer_style_eval.json"
PAUSE_SECONDS = 4
RETRY_WAIT_SECONDS = 25

STYLES = {
    "short": AnswerStyle(level="beginner", tone="friendly", length="short"),
    "medium": AnswerStyle(level="beginner", tone="friendly", length="medium"),
    "long": AnswerStyle(level="beginner", tone="friendly", length="long"),
    "eli12": AnswerStyle(level="beginner", tone="friendly", length="medium", eli12=True),
    "expert": AnswerStyle(level="expert", tone="technical", length="medium"),
}

QUESTIONS = [
    {"id": "S1", "dataset": "baking", "kind": "multi-step answer",
     "question": "How do I stop my cookies from spreading?"},
    {"id": "S2", "dataset": "baking", "kind": "explanation",
     "question": "Why are my brownies cakey instead of fudgy?"},
    {"id": "S3", "dataset": "kestrel", "kind": "technical (hard for ELI12)",
     "question": "What does error KST-2044 mean and how do I fix it?"},
    {"id": "S4", "dataset": "kestrel", "kind": "policy with dates",
     "question": "Can I get a refund on my annual plan 45 days after it renewed?"},
    {"id": "S5", "dataset": "baking", "kind": "not in the documents (must be refused)",
     "question": "How long should I boil fresh pasta?"},
]


def plain_text(markdown: str) -> str:
    text = re.sub(r"[#*_`>\[\]()]", " ", markdown)
    return re.sub(r"\s+", " ", text).strip()


def syllables(word: str) -> int:
    word = word.lower()
    groups = re.findall(r"[aeiouy]+", word)
    count = len(groups) - (1 if word.endswith("e") and len(groups) > 1 else 0)
    return max(1, count)


def flesch_reading_ease(text: str) -> float | None:
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
    sentences = max(1, len(re.findall(r"[.!?]+(\s|$)", text)))
    if not words:
        return None
    syllable_count = sum(syllables(word) for word in words)
    return round(206.835 - 1.015 * len(words) / sentences - 84.6 * syllable_count / len(words), 1)


def ask(question: dict, style: AnswerStyle) -> dict:
    for attempt in (1, 2):
        trace = create_trace("question")
        started = time.perf_counter()
        try:
            response = ask_question(
                question=question["question"],
                dataset=question["dataset"],
                retrievers=["dense", "bm25"],
                trace=trace,
                style=style,
            )
            trace.finish("completed")
            break
        except (RateLimitError, APIStatusError) as exc:
            trace.finish("failed")
            if attempt == 2:
                return {"outcome": "provider_error", "error": type(exc).__name__}
            time.sleep(RETRY_WAIT_SECONDS)
        except LLMResponseError as exc:
            trace.finish("failed")
            return {"outcome": "invalid_response", "error": str(exc)[:160]}
    latency_ms = round((time.perf_counter() - started) * 1000)

    spans = get_trace(trace.trace_id)["spans"]
    generation = next((span for span in spans if span["name"] == "llm_generation"), {})
    attributes = generation.get("attributes", {})
    text = plain_text(response.answer)
    return {
        "outcome": response.status,
        "words": len(text.split()),
        "flesch": flesch_reading_ease(text),
        "citations": len(response.references),
        "glossary_entries": len(response.glossary),
        "glossary_terms": [entry.term for entry in response.glossary],
        "dropped_glossary_entries": attributes.get("dropped_glossary_entries", 0),
        "input_tokens": attributes.get("input_tokens"),
        "output_tokens": attributes.get("output_tokens"),
        "cost_usd": attributes.get("cost_usd"),
        "latency_ms": latency_ms,
        "generation_ms": generation.get("duration_ms"),
        "style_recorded_in_trace": all(
            key in attributes for key in ("style_level", "style_tone", "style_length", "style_eli12")
        ),
        "answer": response.answer,
    }


def summarise(rows: list[dict]) -> dict:
    by_style = {}
    for name in STYLES:
        answered = [r for r in rows if r["style"] == name and r["outcome"] == "answered"]
        def mean(key, digits=2):
            values = [r[key] for r in answered if r.get(key) is not None]
            return round(statistics.mean(values), digits) if values else None
        by_style[name] = {
            "answered": len(answered),
            "mean_words": mean("words"),
            "mean_flesch": mean("flesch"),
            "mean_glossary_entries": mean("glossary_entries"),
            "mean_output_tokens": mean("output_tokens"),
            "mean_cost_usd": mean("cost_usd", 6),
            "mean_latency_ms": mean("latency_ms"),
        }

    checks = []
    for question in QUESTIONS:
        result = {r["style"]: r for r in rows if r["id"] == question["id"]}
        words = [result[s].get("words") for s in ("short", "medium", "long")]
        answered = [result[s]["outcome"] == "answered" for s in STYLES]
        checks.append({
            "id": question["id"],
            "kind": question["kind"],
            "length_order_holds": (
                all(isinstance(w, int) for w in words) and words[0] < words[1] < words[2]
            ),
            "words_short_medium_long": words,
            "eli12_easier_than_expert": (
                result["eli12"].get("flesch") is not None
                and result["expert"].get("flesch") is not None
                and result["eli12"]["flesch"] > result["expert"]["flesch"]
            ),
            "flesch_eli12_expert": [result["eli12"].get("flesch"), result["expert"].get("flesch")],
            "outcomes": {s: result[s]["outcome"] for s in STYLES},
            "refused_in_every_style": not any(answered),
            "every_answer_cited": all(
                result[s].get("citations", 0) > 0 for s in STYLES if result[s]["outcome"] == "answered"
            ),
            "style_recorded_in_every_trace": all(
                result[s].get("style_recorded_in_trace", False) for s in STYLES if "style_recorded_in_trace" in result[s]
            ),
        })
    return {"by_style": by_style, "per_question": checks}


def main() -> None:
    rows = []
    with tempfile.TemporaryDirectory() as traces:
        # Keep evaluation traces out of the user's own trace database.
        with patch("backend.tracing.TRACE_DB_PATH", Path(traces) / "traces.sqlite3"):
            for question in QUESTIONS:
                for name, style in STYLES.items():
                    time.sleep(PAUSE_SECONDS)
                    row = {"id": question["id"], "dataset": question["dataset"], "style": name,
                           "question": question["question"], **ask(question, style)}
                    rows.append(row)
                    print(f"{question['id']} {name:<7} {row['outcome']:<16} "
                          f"words={row.get('words')} flesch={row.get('flesch')} "
                          f"cites={row.get('citations')} gloss={row.get('glossary_entries')} "
                          f"out_tok={row.get('output_tokens')} {row.get('latency_ms')} ms")
    summary = summarise(rows)
    OUTPUT.write_text(json.dumps(
        {"model": MODEL, "styles": {k: v.model_dump() for k, v in STYLES.items()},
         "readability": "Flesch reading ease on the answer text (higher = easier; ~60-70 plain English, 80+ easy)",
         **summary, "results": rows},
        indent=2, ensure_ascii=False,
    ) + "\n")
    print(json.dumps(summary["by_style"], indent=2))
    for check in summary["per_question"]:
        print(check["id"], {k: v for k, v in check.items() if k not in ("id", "kind")})
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
