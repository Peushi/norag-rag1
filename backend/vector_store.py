import chromadb
from chromadb.errors import NotFoundError
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from .documents import PROJECT_ROOT

DB_PATH = PROJECT_ROOT / "chroma_db"
COLLECTION_NAMES = {
    "baking": "bakefix_chunks",
    "kestrel": "bakefix_chunks_kestrel",
}

_embedding_fn = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

_client = chromadb.PersistentClient(path=str(DB_PATH))


def _collection_name(dataset: str) -> str:
    try:
        return COLLECTION_NAMES[dataset]
    except KeyError as exc:
        raise ValueError(f"Unknown retrieval dataset: {dataset}") from exc


def get_collection(dataset: str = "baking"):
    """Create or open the persistent vector collection for a dataset."""
    return _client.get_or_create_collection(
        name=_collection_name(dataset),
        embedding_function=_embedding_fn,
        configuration={"hnsw": {"space": "cosine"}},
    )


def reset_collection(dataset: str = "baking"):
    """Recreate the selected dataset's collection when rebuilding its index."""
    collection_name = _collection_name(dataset)

    try:
        _client.delete_collection(name=collection_name)
    except NotFoundError:
        # the collection does not exist yet.
        pass

    return get_collection(dataset)
