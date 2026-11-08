from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RetrieverName = Literal["dense", "bm25", "graph"]


class RetrievedChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    text: str
    source: str
    position: int = Field(ge=0)
    distance: float


class RetrieveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)
    document_ids: list[str] | None = None
    top_k: int = Field(default=3, ge=1, le=20)
    retrievers: list[RetrieverName] = Field(
        default_factory=lambda: ["dense"],
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_retrievers(self):
        if len(set(self.retrievers)) != len(self.retrievers):
            raise ValueError("retrievers cannot contain duplicates")
        return self


class AskRequest(RetrieveRequest):
    include_path_context: bool = False

    @model_validator(mode="after")
    def validate_path_context_selection(self):
        if self.include_path_context and "graph" not in self.retrievers:
            raise ValueError("include_path_context requires graph retrieval")
        return self


class PathSupportingChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    source: str
    position: int = Field(ge=0)
    text: str


class PathContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paths: list[dict[str, Any]]
    supporting_chunks: list[PathSupportingChunk]


class RetrieverContribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retriever: RetrieverName
    rank: int = Field(ge=1)
    score: float | None = None
    score_type: str | None = None

    @model_validator(mode="after")
    def validate_typed_score(self):
        if (self.score is None) != (self.score_type is None):
            raise ValueError("score and score_type must be provided together")
        if self.score_type is not None and not self.score_type.strip():
            raise ValueError("score_type cannot be empty")
        return self


class FusedRetrievedChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    text: str
    source: str
    position: int = Field(ge=0)
    final_rank: int = Field(ge=1)
    final_score: float
    retrievers: list[RetrieverContribution]


class RetrieveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunks: list[FusedRetrievedChunk]
    retrievers: list[RetrieverName]
    graph_paths: list[dict[str, Any]] = Field(default_factory=list)
    path_context: PathContext | None = None


class Reference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    source: str
    position: int = Field(ge=0)
    quote: str


AnswerReference = Reference


class AskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["answered", "not_found"]
    answer: str
    references: list[Reference] = Field(default_factory=list)
    retrieval: RetrieveResponse | None = None

    @model_validator(mode="after")
    def validate_references(self):
        if self.status == "not_found" and self.references:
            raise ValueError("not_found responses must not contain references.")
        if self.status == "answered" and not self.references:
            raise ValueError("answered responses must include at least one reference.")
        return self


class LLMAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["answered", "not_found"]
    answer: str = Field(min_length=1, pattern=r".*\S.*")
    cited_chunk_ids: list[str] = Field(default_factory=list)


class APIErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    retryable: bool = False


class APIErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: APIErrorDetail


class SourceChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    text: str
    source: str
    position: int = Field(ge=0)
    distance: float


class ChunkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk: SourceChunk


class DocumentSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    size_bytes: int


class DocumentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documents: list[DocumentSummary]


class SettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_size: int = Field(default=800, ge=100, le=2000)
    overlap: int = Field(default=80, ge=0, le=1000)
    top_k: int = Field(default=3, ge=1, le=20)
    relevance_threshold: float | None = Field(default=None, ge=0.0, le=2.0)

    @model_validator(mode="after")
    def validate_chunk_overlap(self):
        if self.overlap >= self.chunk_size:
            raise ValueError("overlap must be smaller than chunk_size")
        return self


EvaluationDataset = Literal["baking", "kestrel"]
EvaluationRunStatus = Literal["queued", "running", "completed", "failed"]


class EvaluationRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: EvaluationDataset
    top_k: int = Field(default=5, ge=1, le=20)
    chunk_size: int = Field(default=800, ge=100, le=2000)
    overlap: int = Field(default=80, ge=0, le=1000)
    max_distance: float | None = Field(default=None, ge=0.0, le=2.0)
    limit: int | None = Field(default=None, ge=1, le=1000)

    @model_validator(mode="after")
    def validate_chunk_overlap(self):
        if self.overlap >= self.chunk_size:
            raise ValueError("overlap must be smaller than chunk_size")
        return self


class EvaluationRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    dataset: EvaluationDataset
    status: EvaluationRunStatus
    top_k: int
    chunk_size: int
    overlap: int
    max_distance: float | None
    limit: int | None
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None


class EvaluationResultsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    dataset: EvaluationDataset
    results: list[dict[str, Any]]


class RetrievalMetricValues(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hit_rate: float | None
    recall: float | None


class RetrievalMetricSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answerable_questions: int = Field(ge=0)
    excluded_questions: int = Field(ge=0)
    metrics: dict[str, RetrievalMetricValues]


class RetrievalEvidenceChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    rank: int = Field(ge=1)


class RetrievalEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    quote: str
    boundary_split: bool
    matched_chunks: list[RetrievalEvidenceChunk]


class RetrievalPassage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    rank: int = Field(ge=1)
    text: str
    source: str
    position: int = Field(ge=0)
    distance: float
    relevant: bool
    matched_evidence_quotes: list[str]


class RetrievalQuestionMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hit: bool
    recall: float = Field(ge=0.0, le=1.0)
    matched_evidence: int = Field(ge=0)
    expected_evidence: int = Field(ge=0)


class RetrievalQuestionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    question: str
    type: str
    answerable: bool
    evidence: list[RetrievalEvidence]
    retrieval_metrics: dict[str, RetrievalQuestionMetric] | None
    evaluation_chunks: list[RetrievalPassage]

    @model_validator(mode="after")
    def validate_answerability_metrics(self):
        if self.answerable != (self.retrieval_metrics is not None):
            raise ValueError(
                "Only answerable questions must have retrieval metrics."
            )
        if self.retrieval_metrics is not None and set(self.retrieval_metrics) != {
            "1",
            "3",
            "5",
            "10",
        }:
            raise ValueError("Retrieval metrics must be provided at k=1,3,5,10.")
        return self


class RetrievalConfigurationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config_id: str
    chunk_size: int
    overlap: int
    top_k: int
    max_distance: float | None
    limit: int | None
    generate_answers: bool
    top_k_values: list[int]
    answerable_questions: int = Field(ge=0)
    excluded_questions: int = Field(ge=0)
    metrics: dict[str, RetrievalMetricValues]
    question_type_breakdown: dict[str, RetrievalMetricSummary]
    questions: list[RetrievalQuestionResult]


class RetrievalComparisonResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment_id: str
    dataset: EvaluationDataset
    embedding_model: str
    distance_metric: str
    relevance_rule: str
    recall_averaging: str
    configurations: list[RetrievalConfigurationResult]


class WordEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    word: str
    occurrence_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)


class WordChunkMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    source: str
    position: int = Field(ge=0)
    text: str
    occurrence_count: int = Field(ge=1)
    matched_words: list[str] = Field(default_factory=list)


class WordVocabularyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: EvaluationDataset
    chunk_size: int
    overlap: int
    total_words: int = Field(ge=0)
    matching_words: int = Field(ge=0)
    offset: int = Field(ge=0)
    words: list[WordEntry]


class WordChunksResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: EvaluationDataset
    chunk_size: int
    overlap: int
    word: str
    occurrence_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    chunks: list[WordChunkMatch]


class WordQuestionAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: EvaluationDataset
    question: str = Field(min_length=1, max_length=4000)
    chunk_size: int = Field(default=800, ge=100, le=2000)
    overlap: int = Field(default=80, ge=0, le=1000)

    @model_validator(mode="after")
    def validate_chunk_overlap(self):
        if self.overlap >= self.chunk_size:
            raise ValueError("overlap must be smaller than chunk_size")
        return self


class WordQuestionAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: EvaluationDataset
    chunk_size: int
    overlap: int
    words_found: list[WordEntry]
    words_missing: list[str]
    matching_chunks: list[WordChunkMatch]


class WordQuestionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    question: str
    type: str = "other"


class WordQuestionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: EvaluationDataset
    questions: list[WordQuestionSummary]
