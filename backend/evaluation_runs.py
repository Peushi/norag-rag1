from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.documents import PROJECT_ROOT
from backend.schemas import EvaluationRunRequest, EvaluationRunResponse

RUNS_DIR = PROJECT_ROOT / "evaluation" / "results" / "runs"

_lock = threading.Lock()
_active_datasets: set[str] = set()


class EvaluationAlreadyRunningError(RuntimeError):
    pass


class EvaluationRunNotFoundError(LookupError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_directory(run_id: str) -> Path:
    try:
        normalized_id = str(uuid.UUID(run_id))
    except ValueError as exc:
        raise EvaluationRunNotFoundError(run_id) from exc
    return RUNS_DIR / normalized_id


def _write_metadata(metadata: dict[str, Any], run_directory: Path) -> None:
    temporary_path = run_directory / "metadata.json.tmp"
    temporary_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(run_directory / "metadata.json")


def get_run(run_id: str) -> EvaluationRunResponse:
    run_directory = _run_directory(run_id)
    metadata_path = run_directory / "metadata.json"
    if not metadata_path.is_file():
        raise EvaluationRunNotFoundError(run_id)

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return EvaluationRunResponse.model_validate(metadata)


def create_run(request: EvaluationRunRequest) -> EvaluationRunResponse:
    with _lock:
        if request.dataset in _active_datasets:
            raise EvaluationAlreadyRunningError(
                f"An evaluation for '{request.dataset}' is already running."
            )
        _active_datasets.add(request.dataset)

    run_id = str(uuid.uuid4())
    run_directory = RUNS_DIR / run_id
    try:
        run_directory.mkdir(parents=True, exist_ok=False)
        metadata = {
            "run_id": run_id,
            "dataset": request.dataset,
            "status": "queued",
            "top_k": request.top_k,
            "chunk_size": request.chunk_size,
            "overlap": request.overlap,
            "max_distance": request.max_distance,
            "limit": request.limit,
            "retrievers": request.retrievers,
            "compare_path_context": request.compare_path_context,
            "generate_answers": request.generate_answers,
            "created_at": _now(),
            "started_at": None,
            "completed_at": None,
            "error": None,
        }
        _write_metadata(metadata, run_directory)
    except Exception:
        with _lock:
            _active_datasets.discard(request.dataset)
        raise

    return EvaluationRunResponse.model_validate(metadata)


def execute_run(run_id: str, request: EvaluationRunRequest) -> None:
    run_directory = _run_directory(run_id)
    metadata_path = run_directory / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["status"] = "running"
    metadata["started_at"] = _now()
    _write_metadata(metadata, run_directory)

    try:
        from evaluation.rag_evaluation import run_evaluation

        run_evaluation(
            dataset=request.dataset,
            top_k=request.top_k,
            chunk_size=request.chunk_size,
            overlap=request.overlap,
            max_distance=request.max_distance,
            output_path=run_directory / "results.jsonl",
            limit=request.limit,
            retrievers=request.retrievers,
            compare_path_context=request.compare_path_context,
            generate_answers=request.generate_answers,
        )
        metadata["status"] = "completed"
    except Exception as exc:
        metadata["status"] = "failed"
        metadata["error"] = str(exc)
    finally:
        metadata["completed_at"] = _now()
        try:
            _write_metadata(metadata, run_directory)
        finally:
            with _lock:
                _active_datasets.discard(request.dataset)


def get_run_results(run_id: str) -> list[dict[str, Any]]:
    run_directory = _run_directory(run_id)
    run = get_run(run_id)
    if run.status != "completed":
        raise RuntimeError(f"Evaluation run is {run.status}, not completed.")

    results_path = run_directory / "results.jsonl"
    if not results_path.is_file():
        raise RuntimeError("Completed evaluation results file is missing.")

    results = []
    with results_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"Invalid JSON in evaluation results at line {line_number}."
                ) from exc
    return results
