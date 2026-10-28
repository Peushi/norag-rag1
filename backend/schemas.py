from typing import Literal

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
    quote: str


class AskResponse(BaseModel):
    status: Literal["answered", "not_found"]
    answer: str
    references: list[Reference] = Field(default_factory=list)


class LLMAnswer(BaseModel):
    status: Literal["answered", "not_found"]
    answer: str = Field(min_length=1, pattern=r".*\S.*")
    cited_chunk_ids: list[str] = Field(default_factory=list)
