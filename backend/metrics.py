"""Usage, latency and cost, computed only from stored traces (V4, Part A bonus).

Nothing here is logged separately: every number is derived from the traces
in the SQLite trace store, so the page and the traces can never disagree.

Definitions (also in the decision log):
- A question is one `question` trace.
- Outcome: `answered` / `abstained` come from the trace outcome (`answered`,
  `not_found`); a failed trace is `invalid` when a step failed with
  LLMResponseError (the model's answer was rejected by validation), otherwise
  `error` (provider unavailable, timeout, retrieval error, rejected request,
  crash). A trace still running is `in_progress`.
- Latency: a request is completed_at - started_at; a step is its span's
  duration. p50/p95 use the nearest-rank method.
- Tokens and cost per question come from the `llm_generation` span.
- Indexing cost per document: concept-map builds are the only indexing step
  that calls an LLM; their `graph_extraction` spans' cost divided by the
  documents the build fully read (new + changed - left for the next build -
  failed and retried later), so a retried document is counted once.
  Uploads and index rebuilds embed locally, so they cost $0.
- Personal data removed: the `pii_redaction` span's counts (Presidio on the
  question, email/phone/secret patterns on the whole prompt); counts and
  types only, never values.
- Days are UTC calendar days.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from backend import tracing

QUESTION_STEP_ORDER = [
    "index_rebuild", "retrieval", "pii_redaction", "llm_generation",
    "response_validation", "citation_verification",
]
OUTCOMES = ["answered", "abstained", "invalid", "error", "in_progress"]


def load_traces(days: int) -> list[dict[str, Any]]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with tracing._database_connection() as connection:
        rows = connection.execute(
            "SELECT operation, status, outcome, started_at, completed_at, spans "
            "FROM traces WHERE started_at >= ? ORDER BY started_at",
            (cutoff,),
        ).fetchall()
    return [
        {
            "operation": row["operation"],
            "status": row["status"],
            "outcome": row["outcome"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "spans": json.loads(row["spans"]),
        }
        for row in rows
    ]


def percentile(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile: the smallest value with at least p% of values at or below it."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return round(ordered[rank - 1], 1)


def classify_question(trace: dict) -> str:
    if trace["status"] == "running":
        return "in_progress"
    if trace["outcome"] == "answered":
        return "answered"
    if trace["outcome"] == "not_found":
        return "abstained"
    if any(span.get("error_type") == "LLMResponseError" for span in trace["spans"]):
        return "invalid"
    return "error"


def _duration_ms(trace: dict) -> float | None:
    if not trace.get("completed_at"):
        return None
    started = datetime.fromisoformat(trace["started_at"])
    completed = datetime.fromisoformat(trace["completed_at"])
    return (completed - started).total_seconds() * 1000


def _latency_table(traces: list[dict], order: list[str]) -> dict:
    requests = [d for d in (_duration_ms(t) for t in traces) if d is not None]
    steps: dict[str, list[float]] = defaultdict(list)
    for trace in traces:
        for span in trace["spans"]:
            steps[span["name"]].append(span["duration_ms"])
    names = [n for n in order if n in steps] + sorted(n for n in steps if n not in order)
    return {
        "request": {"count": len(requests), "p50_ms": percentile(requests, 50), "p95_ms": percentile(requests, 95)},
        "steps": [
            {"step": name, "count": len(steps[name]),
             "p50_ms": percentile(steps[name], 50), "p95_ms": percentile(steps[name], 95)}
            for name in names
        ],
    }


def _number(value) -> float:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def compute_metrics(traces: list[dict], days: int) -> dict:
    questions = [t for t in traces if t["operation"] == "question"]
    indexing = [t for t in traces if t["operation"] == "indexing"]

    # Volume and outcomes.
    outcome_counts = {name: 0 for name in OUTCOMES}
    for trace in questions:
        outcome_counts[classify_question(trace)] += 1

    # Tokens and cost per question (only questions that reached the LLM).
    llm_calls = []
    for trace in questions:
        generation = next((s for s in trace["spans"] if s["name"] == "llm_generation"), None)
        if generation:
            attributes = generation["attributes"]
            llm_calls.append({
                "input_tokens": _number(attributes.get("input_tokens")),
                "output_tokens": _number(attributes.get("output_tokens")),
                "cost_usd": _number(attributes.get("cost_usd")),
            })
    count = len(llm_calls)
    total = {key: sum(call[key] for call in llm_calls) for key in ("input_tokens", "output_tokens", "cost_usd")}
    per_question = {
        "questions_with_llm_call": count,
        "mean_input_tokens": round(total["input_tokens"] / count, 1) if count else None,
        "mean_output_tokens": round(total["output_tokens"] / count, 1) if count else None,
        "mean_cost_usd": round(total["cost_usd"] / count, 6) if count else None,
        "p95_cost_usd": percentile([c["cost_usd"] for c in llm_calls], 95),
        "total_input_tokens": total["input_tokens"],
        "total_output_tokens": total["output_tokens"],
        "total_cost_usd": round(total["cost_usd"], 6),
    }
    if per_question["p95_cost_usd"] is not None:
        # percentile() rounds to 0.1 for milliseconds; costs need more precision.
        costs = sorted(c["cost_usd"] for c in llm_calls)
        per_question["p95_cost_usd"] = round(costs[max(1, math.ceil(0.95 * len(costs))) - 1], 6)

    # Personal data removed before the LLM call (counts and types only).
    checked = with_personal_data = removed = 0
    by_type: dict[str, int] = defaultdict(int)
    for trace in questions:
        redaction = next((s for s in trace["spans"] if s["name"] == "pii_redaction"), None)
        if not redaction or "user_text_redactions" not in redaction["attributes"]:
            continue  # traces from before redaction counts were recorded
        checked += 1
        attributes = redaction["attributes"]
        items = _number(attributes.get("user_text_redactions")) + _number(attributes.get("pattern_redactions"))
        if items:
            with_personal_data += 1
            removed += items
        for key in ("user_text_redaction_types", "pattern_redaction_types"):
            for part in str(attributes.get(key) or "").split(","):
                if ":" in part:
                    kind, number = part.strip().rsplit(":", 1)
                    by_type[kind] += int(number) if number.isdigit() else 0
    privacy = {
        "questions_checked": checked,
        "questions_with_personal_data": with_personal_data,
        "items_removed": removed,
        "by_type": dict(sorted(by_type.items())),
    }

    # Indexing: uploads embed locally ($0); concept-map builds call the LLM.
    uploads = sum(1 for t in indexing if any(s["name"] == "document_storage" for s in t["spans"]))
    rebuilds = sum(1 for t in indexing if any(s["name"] == "embedding_indexing" for s in t["spans"]))
    graph_documents = graph_calls = graph_failed_calls = 0
    graph_tokens = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    for trace in indexing:
        plan = next((s for s in trace["spans"] if s["name"] == "graph_plan"), None)
        if not plan:
            continue
        save = next((s for s in trace["spans"] if s["name"] == "graph_save"), None)
        attributes = plan["attributes"]
        left = _number(save["attributes"].get("documents_left_count")) if save else 0
        failed = _number(save["attributes"].get("failed_document_count")) if save else 0
        # Only documents fully read count; a failed one is retried (and counted) later.
        graph_documents += max(
            0, _number(attributes.get("new_count")) + _number(attributes.get("changed_count")) - left - failed
        )
        for span in trace["spans"]:
            if span["name"] == "graph_extraction":
                graph_calls += 1
                if span.get("error_type"):
                    graph_failed_calls += 1  # no tokens; the document is retried next build
                for key in graph_tokens:
                    graph_tokens[key] += _number(span["attributes"].get(key))
    per_document = {
        "uploads": uploads,
        "index_rebuilds": rebuilds,
        "upload_cost_usd": 0.0,
        "graph_documents_read": graph_documents,
        "graph_llm_calls": graph_calls,
        "graph_failed_calls": graph_failed_calls,
        "graph_input_tokens": graph_tokens["input_tokens"],
        "graph_output_tokens": graph_tokens["output_tokens"],
        "graph_cost_usd": round(graph_tokens["cost_usd"], 6),
        "graph_cost_per_document_usd": (
            round(graph_tokens["cost_usd"] / graph_documents, 6) if graph_documents else None
        ),
        "graph_tokens_per_document": (
            round((graph_tokens["input_tokens"] + graph_tokens["output_tokens"]) / graph_documents, 1)
            if graph_documents else None
        ),
    }

    # Per UTC day.
    daily: dict[str, dict] = defaultdict(lambda: {
        "questions": 0, "answered": 0, "abstained": 0, "invalid": 0, "error": 0,
        "input_tokens": 0, "output_tokens": 0, "question_cost_usd": 0.0, "indexing_cost_usd": 0.0,
    })
    for trace in questions:
        day = daily[trace["started_at"][:10]]
        day["questions"] += 1
        outcome = classify_question(trace)
        if outcome in day:
            day[outcome] += 1
        for span in trace["spans"]:
            if span["name"] == "llm_generation":
                day["input_tokens"] += _number(span["attributes"].get("input_tokens"))
                day["output_tokens"] += _number(span["attributes"].get("output_tokens"))
                day["question_cost_usd"] += _number(span["attributes"].get("cost_usd"))
    for trace in indexing:
        cost = sum(_number(s["attributes"].get("cost_usd")) for s in trace["spans"] if s["name"] == "graph_extraction")
        if cost:
            daily[trace["started_at"][:10]]["indexing_cost_usd"] += cost
    per_day = [
        {"date": date, **{k: (round(v, 6) if isinstance(v, float) else v) for k, v in values.items()},
         "total_cost_usd": round(values["question_cost_usd"] + values["indexing_cost_usd"], 6)}
        for date, values in sorted(daily.items(), reverse=True)
    ]

    return {
        "window_days": days,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "trace_count": len(traces),
        "questions": {"total": len(questions), "outcomes": outcome_counts},
        "latency": _latency_table(
            [t for t in questions if t["status"] != "running"], QUESTION_STEP_ORDER
        ),
        "indexing_latency": _latency_table(
            [t for t in indexing if t["status"] != "running"], []
        ),
        "per_question": per_question,
        "privacy": privacy,
        "per_document": per_document,
        "per_day": per_day,
    }


def get_metrics(days: int = 30) -> dict:
    days = max(1, min(int(days), tracing.TRACE_RETENTION_DAYS))
    return compute_metrics(load_traces(days), days)
