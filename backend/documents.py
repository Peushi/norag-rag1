from pathlib import Path
from typing import TYPE_CHECKING

from .tracing import indexing_operation
from .injection_scanner import scan_document

if TYPE_CHECKING:
    from .llm_service import TraceContext

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = PROJECT_ROOT / "corpus"


def list_documents(corpus_dir: Path = CORPUS_DIR) -> list[Path]:
    """Return supported files in stable order; a missing corpus is empty."""
    corpus_dir = Path(corpus_dir)
    if not corpus_dir.exists():
        return []
    if not corpus_dir.is_dir():
        raise NotADirectoryError(f"Corpus path is not a directory: {corpus_dir}")

    return sorted(
        path
        # searches through its subfolders.
        for path in corpus_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}
    )


def load_documents(corpus_dir: Path = CORPUS_DIR) -> list[dict[str, str]]:
    """Load UTF-8 text unchanged with relative sources; skip blank files.

    Read errors propagate to the caller so an indexing failure is explicit.
    The optional directory allows isolated tests without changing the corpus.
    """
    corpus_dir = Path(corpus_dir)
    documents = []

    for path in list_documents(corpus_dir):
        text = path.read_text(encoding="utf-8")

        if not text.strip():
            continue

        documents.append(
            {
                "source": path.relative_to(corpus_dir).as_posix(),
                "text": text,
            }
        )

    return documents


def resolve_document_path(source: str, *, corpus_dir: Path | None = None) -> Path:
    """resolve a supported document path that remains inside corpus/."""
    if not source or not source.strip():
        raise ValueError("Document name cannot be empty")

    if Path(source).is_absolute():
        raise ValueError("Absolute paths are not allowed")

    if "\\" in source or "\0" in source or ".." in Path(source).parts:
        raise ValueError("Invalid document identifier")

    root = (CORPUS_DIR if corpus_dir is None else Path(corpus_dir)).resolve()
    path = (root / source).resolve()

    if not path.is_relative_to(root):
        raise ValueError("Document must remain inside corpus/")

    if path.suffix.lower() not in {".md", ".txt"}:
        raise ValueError("Only .md and .txt files are supported")

    return path


def dataset_directory(dataset):
    from .retrieval import DATASET_DIRECTORIES
    if dataset not in DATASET_DIRECTORIES:
        raise ValueError("Unknown document dataset")
    return DATASET_DIRECTORIES[dataset]


def validate_new_document(source, content, *, dataset="baking"):
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Document cannot be empty")
    path = resolve_document_path(source, corpus_dir=dataset_directory(dataset))
    if path.exists():
        raise FileExistsError("Document already exists")
    return path


def _save_document(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    file = path.open("x", encoding="utf-8")
    try:
        with file:
            file.write(content)
    except Exception:
        path.unlink(missing_ok=True)
        raise


def add_document(source: str, content: str) -> str:
    """Low-level additions also fail closed; uploads use the quarantine wrapper."""
    path = validate_new_document(source, content)
    if scan_document(content):
        raise ValueError("Document requires quarantine review")
    _save_document(path, content)
    return source


def delete_document(source: str) -> str:
    """Remove a document from corpus/."""
    path = resolve_document_path(source)

    if not path.is_file():
        raise FileNotFoundError(f"Document not found: {source}")

    path.unlink()
    return source


def _publish_and_reindex(source, content, *, dataset, chunk_size, overlap, trace):
    """Publish only screened or explicitly approved content; fail closed on error."""
    from .retrieval import rebuild_index, reset_collection
    from .index_settings import load_settings, validate_settings

    settings = load_settings()
    validate_settings(
        settings["chunk_size"] if chunk_size is None else chunk_size,
        settings["overlap"] if overlap is None else overlap,
    )
    path = validate_new_document(source, content, dataset=dataset)
    with trace.span("document_storage", attributes={"dataset": dataset}):
        _save_document(path, content)
    try:
        with trace.span("index_rebuild", attributes={"dataset": dataset}):
            stats = rebuild_index(chunk_size=chunk_size, overlap=overlap, dataset=dataset, trace=trace)
    except Exception:
        with trace.span("index_rollback", attributes={"dataset": dataset}):
            path.unlink(missing_ok=True)
            # Clear completed batches from a failed build before a retry.
            reset_collection(dataset)
        raise
    return {"source": source, "index": stats}


@indexing_operation
def add_document_and_reindex(
    source: str,
    content: str,
    *,
    chunk_size: int | None = None,
    overlap: int | None = None,
    dataset: str = "baking",
    trace: "TraceContext | None" = None,
) -> dict:
    """Validate and scan BEFORE corpus writes; suspicious uploads stay outside."""
    with trace.span("document_validation") as span:
        validate_new_document(source, content, dataset=dataset)
        span.set_attribute("dataset", dataset)
    with trace.span("injection_scanning") as span:
        findings = scan_document(content)
        span.set_attribute("detection_count", len(findings))
        span.set_attribute("rule_ids", ",".join(sorted({f["rule_id"] for f in findings})))
    if findings:
        from .quarantine import store_quarantined_document
        return store_quarantined_document(source, content, findings, dataset=dataset, trace=trace)
    result = _publish_and_reindex(source, content, dataset=dataset,
                                  chunk_size=chunk_size, overlap=overlap, trace=trace)
    return {**result, "status": "indexed", "dataset": dataset, "findings": []}


@indexing_operation
def delete_document_and_reindex(
    source: str,
    *,
    chunk_size: int | None = None,
    overlap: int | None = None,
    trace: "TraceContext | None" = None,
) -> dict:
    """Delete a document and rebuild using saved settings unless overridden.

    failure restores the file state only; Chroma may need another rebuild.
    """
    from .retrieval import rebuild_index

    path = resolve_document_path(source)
    if not path.is_file():
        raise FileNotFoundError(source)

    original_content = path.read_bytes()
    path.unlink()
    try:
        stats = rebuild_index(chunk_size=chunk_size, overlap=overlap, trace=trace)
    except Exception:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(original_content)
        raise

    return {"source": source, "index": stats}
