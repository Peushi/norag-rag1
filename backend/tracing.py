
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRACE_DB_PATH = Path(
    os.getenv(
        "BAKEFIX_TRACE_DB",
        str(PROJECT_ROOT / ".bakefix" / "traces.sqlite3"),
    )
)
TRACE_RETENTION_DAYS = 30
_ATTRIBUTE_KEY = re.compile(r"^[a-z][a-z0-9_.-]{0,79}$")
_ATTRIBUTE_TYPES = (str, int, float, bool)
_FORBIDDEN_ATTRIBUTE_KEY_PARTS = (
    "api_key",
    "document_text",
    "chunk_text",
    "prompt",
    "question",
    "email",
    "phone",
    "name",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    TRACE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(TRACE_DB_PATH, timeout=5)
    connection.row_factory = sqlite3.Row

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS traces (
                trace_id TEXT PRIMARY KEY,
                operation TEXT NOT NULL,
                status TEXT NOT NULL,
                outcome TEXT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                spans TEXT NOT NULL
            )
            """
        )
    except Exception:
        connection.close()
        raise

    return connection


@contextmanager
def _database_connection() -> Iterator[sqlite3.Connection]:
    """Open a database connection and always commit/rollback and close it."""
    connection = _connect()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _purge_expired(connection: sqlite3.Connection) -> None:
    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=TRACE_RETENTION_DAYS)
    ).isoformat()
    connection.execute(
        """
        DELETE FROM traces
        WHERE COALESCE(completed_at, started_at) < ?
        """,
        (cutoff,),
    )


def create_trace(operation: str) -> StoredTraceContext:
    if not operation or not operation.strip():
        raise ValueError("Trace operation must be non-empty.")

    trace_id = uuid4().hex
    started_at = _utc_now()

    with _database_connection() as connection:
        _purge_expired(connection)
        connection.execute(
            """
            INSERT INTO traces (
                trace_id, operation, status, outcome, started_at, completed_at, spans
            ) VALUES (?, ?, 'running', NULL, ?, NULL, '[]')
            """,
            (trace_id, operation, started_at),
        )

    return StoredTraceContext(trace_id)


def get_trace(trace_id: str) -> dict[str, Any] | None:
    with _database_connection() as connection:
        _purge_expired(connection)
        row = connection.execute(
            """
            SELECT trace_id, operation, status, outcome, started_at, completed_at, spans
            FROM traces WHERE trace_id = ?
            """,
            (trace_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "trace_id": row["trace_id"],
        "operation": row["operation"],
        "status": row["status"],
        "outcome": row["outcome"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "spans": json.loads(row["spans"]),
    }


def _validate_attribute(key: str, value: str | int | float | bool) -> None:
    if not isinstance(key, str) or not _ATTRIBUTE_KEY.fullmatch(key):
        raise ValueError("Trace attribute keys must be lowercase metadata names.")
    if any(part in key for part in _FORBIDDEN_ATTRIBUTE_KEY_PARTS):
        raise ValueError(f"Trace attribute '{key}' is not permitted.")
    if type(value) not in _ATTRIBUTE_TYPES:
        raise TypeError("Trace attributes must be strings, numbers, or booleans.")
    if isinstance(value, str) and len(value) > 200:
        raise ValueError("Trace string attributes must not exceed 200 characters.")


class StoredTraceContext:
    """SQLite-backed implementation of the generation trace protocol."""

    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        self._lock = threading.Lock()

    def span(
        self,
        name: str,
        *,
        attributes: Mapping[str, str | int | float | bool] | None = None,
    ) -> TraceSpan:
        if not name or not name.strip():
            raise ValueError("Span name must be non-empty.")
        return TraceSpan(self, name, attributes)

    def set_outcome(self, outcome: str) -> None:
        if not outcome or not outcome.strip():
            raise ValueError("Trace outcome must be non-empty.")

        with _database_connection() as connection:
            cursor = connection.execute(
                "UPDATE traces SET outcome = ? WHERE trace_id = ?",
                (outcome, self.trace_id),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(f"Trace '{self.trace_id}' does not exist.")

    def finish(self, status: str) -> None:
        if status not in {"completed", "failed"}:
            raise ValueError("Final trace status must be completed or failed.")

        with _database_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE traces SET status = ?, completed_at = ?
                WHERE trace_id = ? AND status = 'running'
                """,
                (status, _utc_now(), self.trace_id),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(
                    f"Trace '{self.trace_id}' is missing or already finalized."
                )

    def _append_span(self, span: dict[str, Any]) -> None:
        with self._lock, _database_connection() as connection:
            row = connection.execute(
                "SELECT spans FROM traces WHERE trace_id = ?",
                (self.trace_id,),
            ).fetchone()
            if row is None:
                raise RuntimeError(f"Trace '{self.trace_id}' does not exist.")

            spans = json.loads(row["spans"])
            spans.append(span)

            connection.execute(
                "UPDATE traces SET spans = ? WHERE trace_id = ?",
                (json.dumps(spans, ensure_ascii=False), self.trace_id),
            )


class TraceSpan:
    def __init__(
        self,
        trace: StoredTraceContext,
        name: str,
        attributes: Mapping[str, str | int | float | bool] | None,
    ):
        self._trace = trace
        self._name = name
        self._attributes: dict[str, str | int | float | bool] = {}
        self._started_at: str | None = None
        self._started_clock: float | None = None

        for key, value in (attributes or {}).items():
            self.set_attribute(key, value)

    def __enter__(self) -> TraceSpan:
        if self._started_at is not None:
            raise RuntimeError("A trace span cannot be entered more than once.")

        self._started_at = _utc_now()
        self._started_clock = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        if self._started_at is None or self._started_clock is None:
            raise RuntimeError("Trace span exited without being entered.")

        completed_at = _utc_now()
        span: dict[str, Any] = {
            "name": self._name,
            "status": "failed" if exc_type is not None else "completed",
            "started_at": self._started_at,
            "completed_at": completed_at,
            "duration_ms": round(
                (time.perf_counter() - self._started_clock) * 1000,
                3,
            ),
            "attributes": self._attributes,
        }

        if exc_type is not None:
            span["error_type"] = exc_type.__name__

        self._trace._append_span(span)
        return False

    def set_attribute(
        self,
        key: str,
        value: str | int | float | bool,
    ) -> None:
        _validate_attribute(key, value)
        self._attributes[key] = value


# Reuse the caller's trace across nested rebuilds; ownership stays with its creator.
_indexing_trace = ContextVar("bakefix_indexing_trace", default=None)


@contextmanager
def use_indexing_trace(trace):
    token = _indexing_trace.set(trace)
    try:
        yield trace
    finally:
        _indexing_trace.reset(token)


def indexing_operation(function):
    """Trace an indexing entry point without creating nested duplicate traces."""
    @wraps(function)
    def wrapped(*args, trace=None, **kwargs):
        current = trace if trace is not None else _indexing_trace.get()
        owned = current is None
        if owned:
            current = create_trace("indexing")
        try:
            with use_indexing_trace(current):
                result = function(*args, trace=current, **kwargs)
        except Exception:
            if owned:
                current.set_outcome("failed")
                current.finish("failed")
            raise
        explicit_outcome = result.get("status") if isinstance(result, dict) else None
        if explicit_outcome in {"indexed", "quarantined", "rejected"} and hasattr(current, "set_outcome"):
            current.set_outcome(explicit_outcome)
        if owned:
            partial = isinstance(result, dict) and bool(result.get("failed_chunks"))
            outcome = explicit_outcome if explicit_outcome in {"indexed", "quarantined", "rejected"} else "indexed"
            if partial:
                successes = result.get("statistics", {}).get("successful_calls", 0)
                outcome = "partial" if successes else "failed"
            current.set_outcome(outcome)
            current.finish("failed" if partial else "completed")
        if isinstance(result, dict):
            result = {**result, "trace_id": current.trace_id}
        return result
    return wrapped
