
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# Each corpus has its own vocabulary: Kestrel (a software company's help
# documents) and "My documents" (kitchen documents: recipes, baking notes,
# appliance manuals). The extraction prompt offers only the corpus's own
# types, and triples using another corpus's types are rejected.
KESTREL_ENTITY_TYPES = (
    "ERROR_CODE", "SERVICE", "TEAM", "POLICY", "PRODUCT", "PLAN", "FEATURE", "ROLE", "CHANNEL",
)
KITCHEN_ENTITY_TYPES = (
    "DISH", "INGREDIENT", "EQUIPMENT", "TECHNIQUE", "PROBLEM", "CONDITION",
)

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
    # Kitchen documents
    "DISH",
    "INGREDIENT",
    "EQUIPMENT",
    "TECHNIQUE",
    "PROBLEM",
    "CONDITION",
]

KESTREL_RELATIONS = (
    "HANDLED_BY", "OWNED_BY", "ESCALATES_TO", "HAS_CHANNEL", "REPLACES", "GOVERNED_BY",
    "SUPPORTS", "INCLUDES", "REQUIRES", "AFFECTS_SERVICE", "HAS_CAUSE", "RESOLVED_BY",
)
KITCHEN_RELATIONS = (
    "CAUSES", "FIXES", "PREVENTS", "REQUIRES", "USES", "AFFECTS", "PART_OF", "SUBSTITUTES_FOR",
)

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
    # Kitchen documents
    "CAUSES",
    "FIXES",
    "PREVENTS",
    "USES",
    "AFFECTS",
    "PART_OF",
    "SUBSTITUTES_FOR",
]

# Vocabulary per corpus: (entity types, relation types, how to describe them to the LLM).
GRAPH_VOCABULARIES = {
    "kestrel": (KESTREL_ENTITY_TYPES, KESTREL_RELATIONS, ""),
    "baking": (
        KITCHEN_ENTITY_TYPES,
        KITCHEN_RELATIONS,
        """Meaning of the types:
- DISH: something being made (fudgy brownies, sourdough bread, pie crust)
- INGREDIENT: flour, butter, baking powder, sourdough starter
- EQUIPMENT: tools and appliances (loaf pan, oven thermometer, espresso machine)
- TECHNIQUE: an action or process (chilling the dough, proofing, descaling)
- PROBLEM: something going wrong (cookies spreading, dough not rising, soggy crust)
- CONDITION: a temperature, time, amount or environment (cold kitchen, 30 minutes, hard water)
Relationships read subject -> object: X CAUSES PROBLEM; TECHNIQUE FIXES or PREVENTS
PROBLEM; DISH REQUIRES or USES INGREDIENT/EQUIPMENT; X AFFECTS Y; X PART_OF Y;
INGREDIENT SUBSTITUTES_FOR INGREDIENT.""",
    ),
}


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


class GraphConcept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    type: EntityType


class ConceptNeighbour(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept: GraphConcept
    relation: RelationType
    direction: Literal["incoming", "outgoing"]
    chunk_ids: list[str]


class ConceptNeighbourhood(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept: GraphConcept
    neighbours: list[ConceptNeighbour]


class ConceptListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concepts: list[GraphConcept]


class ConceptNeighbourhoodResponse(ConceptNeighbourhood):
    """A concept's neighbourhood plus the trace recorded for opening it."""

    trace_id: str


class GraphStatusResponse(BaseModel):
    """State of a corpus's concept graph, and what an update would cost."""

    model_config = ConfigDict(extra="forbid")

    dataset: str
    buildable: bool
    built: bool
    up_to_date: bool
    built_at: str | None = None
    document_count: int = 0
    triple_count: int = 0
    new_documents: list[str] = Field(default_factory=list)
    changed_documents: list[str] = Field(default_factory=list)
    removed_documents: list[str] = Field(default_factory=list)
    settings_changed: bool = False
    llm_calls_needed: int = 0
    max_llm_calls_per_build: int = 0
    building: bool = False
    progress_done: int = 0
    progress_total: int = 0
    build_trace_id: str | None = None
    last_error: str | None = None


class GraphBuildResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["started"]
    trace_id: str
