import json
from pathlib import Path

from .documents import PROJECT_ROOT

SETTINGS_PATH = PROJECT_ROOT / "index_settings.json"

DEFAULT_SETTINGS = {
    "chunk_size": 800,
    "overlap": 80,
}


def validate_settings(chunk_size: int, overlap: int) -> None:
    if type(chunk_size) is not int or chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer")

    if type(overlap) is not int or not 0 <= overlap < chunk_size:
        raise ValueError("overlap must be at least 0 and smaller than chunk_size")


def load_settings() -> dict:
    """return saved settings, or defaults if not configured yet."""

    if not SETTINGS_PATH.exists():
        return DEFAULT_SETTINGS.copy()

    with SETTINGS_PATH.open("r", encoding="utf-8") as file:
        settings = json.load(file)

    chunk_size = settings["chunk_size"]
    overlap = settings["overlap"]

    validate_settings(chunk_size, overlap)

    return {
        "chunk_size": chunk_size,
        "overlap": overlap,
    }


def save_settings(chunk_size: int, overlap: int) -> dict:
    """persist the indexing settings."""

    validate_settings(chunk_size, overlap)

    settings = {
        "chunk_size": chunk_size,
        "overlap": overlap,
    }

    # write a temporary file, then replace the old one.
    temporary = SETTINGS_PATH.with_suffix(".json.tmp")

    temporary.write_text(
        json.dumps(settings, indent=2),
        encoding="utf-8",
    )

    temporary.replace(SETTINGS_PATH)

    return settings
