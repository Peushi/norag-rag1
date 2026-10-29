import chromadb
from chromadb.errors import NotFoundError
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from .documents import PROJECT_ROOT

DB_PATH = PROJECT_ROOT / "chroma_db"
COLLECTION_NAME = "bakefix_chunks"

_embedding_fn = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

_client = chromadb.PersistentClient(path=str(DB_PATH))


def get_collection():
    """create or open the persistent vector collection."""

    return _client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=_embedding_fn,
        configuration={"hnsw": {"space": "cosine"}},
    )


def reset_collection():
    """recreate the collection when rebuilding the index."""

    try:
        _client.delete_collection(name=COLLECTION_NAME)
    except NotFoundError:
        # the collection does not exist yet.
        pass

    return get_collection()
