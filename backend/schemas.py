from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class AskRequest(RetrieveRequest):
    pass


class RetrieveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunks: list[RetrievedChunk]


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
