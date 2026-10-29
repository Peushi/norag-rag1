<<<<<<< HEAD
from __future__ import annotations

from typing import Literal

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


class RetrieveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunks: list[RetrievedChunk]


class AskRequest(RetrieveRequest):
    pass


class AnswerReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    source: str
    position: int = Field(ge=0)
=======
﻿from typing import Literal

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    document_ids: list[str] | None = None


class RetrieveRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    document_ids: list[str] | None = None


class RetrievedChunk(BaseModel):
    id: str
    text: str
    source: str
    position: int
    distance: float


class RetrieveResponse(BaseModel):
    chunks: list[RetrievedChunk]


class Reference(BaseModel):
    chunk_id: str
    source: str
    position: int
>>>>>>> origin/main
    quote: str


class AskResponse(BaseModel):
<<<<<<< HEAD
    model_config = ConfigDict(extra="forbid")

    status: Literal["answered", "not_found"]
    answer: str
    references: list[AnswerReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self):
        if self.status == "not_found" and self.references:
            raise ValueError("not_found responses must not contain references.")
        if self.status == "answered" and len(self.references) == 0:
            raise ValueError("answered responses must include at least one reference.")
        return self


class APIErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    retryable: bool = False


class APIErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: APIErrorDetail


class ChunkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk: RetrievedChunk


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

    chunk_size: int = Field(default=600, ge=100, le=2000)
    overlap: int = Field(default=120, ge=0, le=1000)
    top_k: int = Field(default=3, ge=1, le=20)
    relevance_threshold: float | None = Field(default=None, ge=0.0)
=======
    status: Literal["answered", "not_found"]
    answer: str
    references: list[Reference] = Field(default_factory=list)


class LLMAnswer(BaseModel):
    status: Literal["answered", "not_found"]
    answer: str = Field(min_length=1, pattern=r".*\S.*")
    cited_chunk_ids: list[str] = Field(default_factory=list)
>>>>>>> origin/main
