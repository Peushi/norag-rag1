from .documents import load_documents
from .retrieval import rebuild_index, retrieve_chunks


def main():
    documents = load_documents()

    print(f"\nLoaded {len(documents)} documents")

    for document in documents:
        print(f"- {document['source']}")

    print("\nBuilding Chroma index...")

    stats = rebuild_index(
        chunk_size=800,
        overlap=80,
    )

    print("Index stats:", stats)

    question = "The filling of my pie is cooked, but the pastry underneath is still wet. How can I prevent that?"

    print(f"\nQuestion: {question}\n")

    chunks = retrieve_chunks(
        question=question,
        top_k=5,
    )

    for index, chunk in enumerate(chunks, start=1):
        print(f"Result {index}")
        print(f"Source: {chunk['source']}")
        print(f"ID: {chunk['id']}")
        print(f"Position: {chunk['position']}")
        print(f"Cosine distance: {chunk['distance']:.4f}")
        print(f"Text: {chunk['text'][:250]}...")
        print("-" * 50)


if __name__ == "__main__":
    main()
