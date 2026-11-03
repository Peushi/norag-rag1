from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.documents import PROJECT_ROOT
from backend.schemas import (
    RetrievalComparisonResponse,
    RetrievalConfigurationResult,
    RetrievalEvidence,
    RetrievalEvidenceChunk,
    RetrievalMetricSummary,
    RetrievalMetricValues,
    RetrievalPassage,
    RetrievalQuestionMetric,
    RetrievalQuestionResult,
)

RetrievalExperimentId = Literal["retrieval-v2-baking", "retrieval-v2-kestrel"]

EXPERIMENT_DATASETS: dict[RetrievalExperimentId, Literal["baking", "kestrel"]] = {
    "retrieval-v2-baking": "baking",
    "retrieval-v2-kestrel": "kestrel",
}
CONFIGURATIONS = ((800, 80), (400, 40))
K_VALUES = (1, 3, 5, 10)
RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"


class _InputModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _InputMetric(_InputModel):
    hit: bool
    recall: float = Field(ge=0.0, le=1.0)
    matched_evidence: int = Field(ge=0)
    expected_evidence: int = Field(ge=0)


class _InputEvidenceChunk(_InputModel):
    id: str
    rank: int = Field(ge=1)


class _InputEvidence(_InputModel):
    source: str
    quote: str


class _InputEvidenceMatch(_InputModel):
    source: str
    quote: str
    matched_chunks: list[_InputEvidenceChunk]
    boundary_split: bool


class _InputPassage(_InputModel):
    id: str
    text: str
    source: str
    position: int = Field(ge=0)
    distance: float


class _InputQuestion(_InputModel):
    id: str
    question: str
    type: str
    answerable: bool
    chunk_size: int
    overlap: int
    evidence: list[_InputEvidence] = Field(default_factory=list)
    evidence_matches: list[_InputEvidenceMatch] | None = None
    retrieval_metrics: dict[str, _InputMetric] | None = None
    evaluation_chunks: list[_InputPassage] = Field(default_factory=list)
    evaluation_config: dict[str, Any]


class _InputAggregateMetric(_InputModel):
    hit_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    recall: float | None = Field(default=None, ge=0.0, le=1.0)


class _InputAggregate(_InputModel):
    answerable_questions: int = Field(ge=0)
    excluded_questions: int = Field(ge=0)
    metrics: dict[str, _InputAggregateMetric]


class _InputSummary(_InputModel):
    dataset: Literal["baking", "kestrel"]
    chunk_size: int
    overlap: int
    top_k: int
    max_distance: float | None
    limit: int | None
    generate_answers: bool
    configuration_id: str
    embedding_model: str
    distance_metric: str
    k_values: list[int]
    recall_averaging: str
    relevance_rule: str
    overall: _InputAggregate
    by_type: dict[str, _InputAggregate]


class RetrievalComparisonNotFoundError(LookupError):
    pass


class RetrievalComparisonDataError(RuntimeError):
    pass


def _read_jsonl(path: Path, model: type[BaseModel]) -> list[BaseModel]:
    if not path.is_file():
        raise RetrievalComparisonNotFoundError(
            f"Retrieval comparison data is missing: {path.name}"
        )

    records: list[BaseModel] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                records.append(model.model_validate_json(line))
            except (ValidationError, ValueError) as exc:
                raise RetrievalComparisonDataError(
                    f"Invalid retrieval comparison data at "
                    f"{path.name}:{line_number}."
                ) from exc
    return records


def _aggregate(
    aggregate: _InputAggregate,
) -> RetrievalMetricSummary:
    return RetrievalMetricSummary(
        answerable_questions=aggregate.answerable_questions,
        excluded_questions=aggregate.excluded_questions,
        metrics={
            k: RetrievalMetricValues(
                hit_rate=metric.hit_rate,
                recall=metric.recall,
            )
            for k, metric in aggregate.metrics.items()
        },
    )


def _question_result(question: _InputQuestion) -> RetrievalQuestionResult:
    matches = question.evidence_matches or []
    matches_by_quote = {
        (evidence.source, evidence.quote): evidence for evidence in matches
    }
    matched_quotes: dict[str, list[str]] = {}
    for evidence in matches:
        for chunk in evidence.matched_chunks:
            matched_quotes.setdefault(chunk.id, []).append(evidence.quote)

    output_evidence = []
    for evidence in question.evidence:
        match = matches_by_quote.get((evidence.source, evidence.quote))
        if match is None:
            raise RetrievalComparisonDataError(
                f"Evidence match is missing for question {question.id}."
            )
        output_evidence.append(
            RetrievalEvidence(
                source=evidence.source,
                quote=evidence.quote,
                boundary_split=match.boundary_split,
                matched_chunks=[
                    RetrievalEvidenceChunk(id=chunk.id, rank=chunk.rank)
                    for chunk in match.matched_chunks
                ],
            )
        )

    passages = [
        RetrievalPassage(
            id=passage.id,
            rank=rank,
            text=passage.text,
            source=passage.source,
            position=passage.position,
            distance=passage.distance,
            relevant=passage.id in matched_quotes,
            matched_evidence_quotes=matched_quotes.get(passage.id, []),
        )
        for rank, passage in enumerate(question.evaluation_chunks, start=1)
    ]

    metrics = (
        {
            k: RetrievalQuestionMetric(
                hit=metric.hit,
                recall=metric.recall,
                matched_evidence=metric.matched_evidence,
                expected_evidence=metric.expected_evidence,
            )
            for k, metric in question.retrieval_metrics.items()
        }
        if question.retrieval_metrics is not None
        else None
    )
    return RetrievalQuestionResult(
        id=question.id,
        question=question.question,
        type=question.type,
        answerable=question.answerable,
        evidence=output_evidence,
        retrieval_metrics=metrics,
        evaluation_chunks=passages,
    )


def _load_configuration(
    dataset: Literal["baking", "kestrel"],
    chunk_size: int,
    overlap: int,
) -> tuple[_InputSummary, list[_InputQuestion]]:
    stem = f"{dataset}_retrieval_{chunk_size}_{overlap}"
    summary_path = RESULTS_DIR / f"{stem}_summary.jsonl"
    result_path = RESULTS_DIR / f"{stem}.jsonl"

    summaries = _read_jsonl(summary_path, _InputSummary)
    if len(summaries) != 1:
        raise RetrievalComparisonDataError(
            f"Expected exactly one summary record in {summary_path.name}."
        )
    summary = summaries[0]
    if not isinstance(summary, _InputSummary):
        raise RetrievalComparisonDataError(
            f"Invalid summary record in {summary_path.name}."
        )

    question_records = _read_jsonl(result_path, _InputQuestion)
    questions = []
    for record in question_records:
        if not isinstance(record, _InputQuestion):
            raise RetrievalComparisonDataError(
                f"Invalid question record in {result_path.name}."
            )
        if (
            record.evaluation_config.get("dataset") != dataset
            or record.evaluation_config.get("configuration_id")
            != summary.configuration_id
            or record.evaluation_config.get("embedding_model")
            != summary.embedding_model
            or record.evaluation_config.get("distance_metric")
            != summary.distance_metric
            or record.evaluation_config.get("k_values") != summary.k_values
            or record.evaluation_config.get("max_distance")
            != summary.max_distance
            or record.evaluation_config.get("limit") != summary.limit
            or record.chunk_size != chunk_size
            or record.overlap != overlap
        ):
            raise RetrievalComparisonDataError(
                f"Question configuration does not match {result_path.name}."
            )
        questions.append(record)

    if len(questions) != (
        summary.overall.answerable_questions + summary.overall.excluded_questions
    ):
        raise RetrievalComparisonDataError(
            f"Question count does not match the summary in {result_path.name}."
        )
    if (
        sum(question.answerable for question in questions)
        != summary.overall.answerable_questions
    ):
        raise RetrievalComparisonDataError(
            f"Answerability counts do not match the summary in {result_path.name}."
        )

    return summary, questions


def get_retrieval_comparison(
    experiment_id: str,
) -> RetrievalComparisonResponse:
    if experiment_id not in EXPERIMENT_DATASETS:
        raise RetrievalComparisonNotFoundError(experiment_id)

    normalized_experiment_id = experiment_id
    dataset = EXPERIMENT_DATASETS[experiment_id]
    configurations = []
    base_summary: _InputSummary | None = None

    for chunk_size, overlap in CONFIGURATIONS:
        summary, questions = _load_configuration(dataset, chunk_size, overlap)
        if (
            summary.dataset != dataset
            or summary.chunk_size != chunk_size
            or summary.overlap != overlap
        ):
            raise RetrievalComparisonDataError(
                f"Configuration metadata does not match the result file for "
                f"{dataset} {chunk_size}/{overlap}."
            )
        if summary.k_values != list(K_VALUES):
            raise RetrievalComparisonDataError(
                f"Unexpected k values in {dataset} {chunk_size}/{overlap} summary."
            )

        common_metadata = (
            summary.embedding_model,
            summary.distance_metric,
            summary.relevance_rule,
            summary.recall_averaging,
        )
        if base_summary is None:
            base_summary = summary
        elif common_metadata != (
            base_summary.embedding_model,
            base_summary.distance_metric,
            base_summary.relevance_rule,
            base_summary.recall_averaging,
        ) or (
            summary.top_k != base_summary.top_k
            or summary.max_distance != base_summary.max_distance
            or summary.limit != base_summary.limit
            or summary.generate_answers != base_summary.generate_answers
        ):
            raise RetrievalComparisonDataError(
                f"Evaluation metadata differs between configurations for {dataset}."
            )

        configurations.append(
            RetrievalConfigurationResult(
                config_id=summary.configuration_id,
                chunk_size=summary.chunk_size,
                overlap=summary.overlap,
                top_k=summary.top_k,
                max_distance=summary.max_distance,
                limit=summary.limit,
                generate_answers=summary.generate_answers,
                top_k_values=summary.k_values,
                answerable_questions=summary.overall.answerable_questions,
                excluded_questions=summary.overall.excluded_questions,
                metrics={
                    k: RetrievalMetricValues(
                        hit_rate=metric.hit_rate,
                        recall=metric.recall,
                    )
                    for k, metric in summary.overall.metrics.items()
                },
                question_type_breakdown={
                    question_type: _aggregate(aggregate)
                    for question_type, aggregate in summary.by_type.items()
                },
                questions=[_question_result(question) for question in questions],
            )
        )

    if not configurations or base_summary is None:
        raise RetrievalComparisonDataError(
            f"No retrieval comparison configurations are available for {dataset}."
        )

    return RetrievalComparisonResponse(
        experiment_id=normalized_experiment_id,
        dataset=dataset,
        embedding_model=base_summary.embedding_model,
        distance_metric=base_summary.distance_metric,
        relevance_rule=base_summary.relevance_rule,
        recall_averaging=base_summary.recall_averaging,
        configurations=configurations,
    )
