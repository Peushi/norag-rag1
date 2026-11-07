
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

RESOLUTION_FILE = (
    PROJECT_ROOT / "kestrel-kb" / "graph" / "entity_resolution.json"
)


def load_entity_resolutions():
    """Load documented entity-resolution rules."""

    if not RESOLUTION_FILE.exists():
        return {"correct_resolutions": [], "rejected_merges": []}

    with RESOLUTION_FILE.open(encoding="utf-8") as file:
        return json.load(file)


def resolve_entity(name: str, entity_type: str) -> dict:
    """Return the canonical entity while preserving its type."""

    rules = load_entity_resolutions()

    for resolution in rules["correct_resolutions"]:
        alias = resolution["alias"]
        canonical = resolution["canonical"]

        if (
            name.casefold() == alias["name"].casefold()
            and entity_type == alias["entity_type"]
        ):
            return {
                "name": canonical["name"],
                "entity_type": canonical["entity_type"],
            }

    return {
        "name": name,
        "entity_type": entity_type,
    }


def resolve_graph_triples(triples: list[dict]) -> list[dict]:
    resolved = []

    for triple in triples:
        updated = dict(triple)

        # Keep historical replacement relationships unchanged.
        if triple["relation"] == "REPLACES":
            resolved.append(updated)
            continue

        updated["subject"] = resolve_entity(
            triple["subject"]["name"],
            triple["subject"]["entity_type"]
        )

        updated["object"] = resolve_entity(
            triple["object"]["name"],
            triple["object"]["entity_type"]
        )

        resolved.append(updated)

    return resolved