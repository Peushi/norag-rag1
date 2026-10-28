from pathlib import Path

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


def delete_document(source):
    """delete one corpus file identified by its relative path."""
    path = (CORPUS_DIR / source).resolve()
    root = CORPUS_DIR.resolve()

    if not path.is_relative_to(root):
        raise ValueError("Invalid document path")

    if path.suffix.lower() not in {".md", ".txt"}:
        raise ValueError("Unsupported document type")

    if not path.is_file():
        raise FileNotFoundError(source)

    path.unlink()
    return source
