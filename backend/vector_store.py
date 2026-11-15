import chromadb
from chromadb.errors import NotFoundError
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from .documents import PROJECT_ROOT

DB_PATH = PROJECT_ROOT / "chroma_db"
COLLECTION_NAMES = {
    "baking": "bakefix_chunks",
    "kestrel": "bakefix_chunks_kestrel",
}

# Pinned to one Hugging Face commit so embeddings (and the evaluation results
# measured with them) cannot change if the model is updated on the Hub.
# Listed in the AI-BOM (aibom/); tests/test_aibom.py fails if they disagree.
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_MODEL_REPO = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"

_embedding_fn = SentenceTransformerEmbeddingFunction(
    model_name=EMBEDDING_MODEL, revision=EMBEDDING_MODEL_REVISION
)

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
