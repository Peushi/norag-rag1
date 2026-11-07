
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


EntityType = Literal[
    "ERROR_CODE",
    "SERVICE",
    "TEAM",
    "POLICY",
    "PRODUCT",
    "PLAN",
    "FEATURE",
    "ROLE",
    "CHANNEL",
]

RelationType = Literal[
    "HANDLED_BY",
    "OWNED_BY",
    "ESCALATES_TO",
    "HAS_CHANNEL",
    "REPLACES",
    "GOVERNED_BY",
    "SUPPORTS",
    "INCLUDES",
    "REQUIRES",
    "AFFECTS_SERVICE",
    "HAS_CAUSE",
    "RESOLVED_BY",
]


class GraphEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    entity_type: EntityType


class ExtractedTriple(BaseModel):
    """Triple returned by Gemini, before trusted provenance is attached."""

    model_config = ConfigDict(extra="forbid")

    subject: GraphEntity
    relation: RelationType
    object: GraphEntity
    evidence_quote: str = Field(min_length=1)


class GraphTriple(BaseModel):
    """Validated graph triple with its original chunk provenance."""

    model_config = ConfigDict(extra="forbid")

    subject: GraphEntity
    relation: RelationType
    object: GraphEntity
    chunk_id: str = Field(min_length=1)
    evidence_quote: str = Field(min_length=1)


class GraphExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    triples: list[ExtractedTriple] = Field(default_factory=list)
