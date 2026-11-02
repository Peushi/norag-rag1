import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from backend.chunking import chunk_text
from backend.documents import PROJECT_ROOT, load_documents
from backend.llm_service import MODEL, generate_answer
from backend.retrieval import make_chunk_id, filter_by_relevance



EVALUATION_DIR = PROJECT_ROOT / "evaluation"

DATASETS = {
    "baking": {
        "questions": EVALUATION_DIR / "baking_questions.jsonl",
        "documents": PROJECT_ROOT / "corpus",
    },
    "kestrel": {
        "questions": PROJECT_ROOT / "kestrel-kb" / "eval" / "questions.starter.jsonl",
        "documents": PROJECT_ROOT / "kestrel-kb" / "docs",
    },
}


def load_questions(path):
    with path.open("r", encoding="utf-8-sig") as file:
        return [json.loads(line) for line in file if line.strip()]


def build_isolated_index(dataset, documents, chunk_size, overlap):
    index_path = EVALUATION_DIR / "indexes" / dataset
    index_path.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(index_path))

    try:
        client.delete_collection("rag_evaluation")
    except Exception:
        pass

    embedding_fn = SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    collection = client.create_collection(
        name="rag_evaluation",
        embedding_function=embedding_fn,
        configuration={"hnsw": {"space": "cosine"}},
    )

    total_chunks = 0

    for document in documents:
        source = document["source"]

        chunks = chunk_text(
            document["text"],
            chunk_size=chunk_size,
            overlap=overlap,
        )

        ids = [
            make_chunk_id(source, chunk["position"])
            for chunk in chunks
        ]

        for start in range(0, len(chunks), 100):
            batch = chunks[start:start + 100]
            batch_ids = ids[start:start + 100]

            collection.add(
                ids=batch_ids,
                documents=[chunk["text"] for chunk in batch],
                metadatas=[
                    {
                        "source": source,
                        "position": chunk["position"],
                        "start": chunk["start"],
                    }
                    for chunk in batch
                ],
            )

        total_chunks += len(chunks)

    return collection, total_chunks


def retrieve(collection, question, top_k, max_distance):
    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[question],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    chunks = []

    for i, chunk_id in enumerate(results["ids"][0]):
        metadata = results["metadatas"][0][i]

        chunks.append({
            "id": chunk_id,
            "text": results["documents"][0][i],
            "source": metadata["source"],
            "position": metadata["position"],
            "distance": float(results["distances"][0][i]),
        })

    return filter_by_relevance(chunks, max_distance)


def evaluate(args):
    config = DATASETS[args.dataset]

    questions = load_questions(config["questions"])
    if args.limit is not None:
        questions = questions[:args.limit]
    documents = load_documents(config["documents"])

    if not documents:
        raise RuntimeError(
            f"No documents found for dataset: {args.dataset}"
        )

    print(f"Dataset: {args.dataset}")
    print(f"Documents: {len(documents)}")
    print(f"Questions: {len(questions)}")
    print(f"Chunk size: {args.chunk_size}")
    print(f"Overlap: {args.overlap}")
    print(f"Top K: {args.top_k}")

    collection, total_chunks = build_isolated_index(
        args.dataset,
        documents,
        args.chunk_size,
        args.overlap,
    )

    print(f"Indexed chunks: {total_chunks}")

    output_path = (
        EVALUATION_DIR / "results" / f"{args.dataset}_rag.jsonl"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    completed = 0
    errors = 0

    with output_path.open("w", encoding="utf-8") as output:
        for index, item in enumerate(questions, start=1):
            question = item["question"]
            print(f"\n[{index}/{len(questions)}] {item['id']}: {question}")

            retrieved = retrieve(
                collection,
                question,
                args.top_k,
                args.max_distance,
            )

            expected_sources = sorted({
                evidence["source"]
                for evidence in item.get("evidence", [])
            })

            found_sources = sorted({
                chunk["source"] for chunk in retrieved
            })

            retrieval_hit = (
                bool(set(expected_sources) & set(found_sources))
                if expected_sources else None
            )

            try:
                response = generate_answer(question, retrieved)

                result = {
                    **item,
                    "model": MODEL,
                    "top_k": args.top_k,
                    "chunk_size": args.chunk_size,
                    "overlap": args.overlap,
                    "retrieval_hit": retrieval_hit,
                    "retrieved_chunks": retrieved,
                    "retrieved_sources": found_sources,
                    "status": response.status,
                    "model_answer": response.answer,
                    "references": [
                        reference.model_dump()
                        for reference in response.references
                    ],
                    "manual_review": "pending",
                    "error": None,
                }

                completed += 1
                print(f"Status: {response.status}")
                print(f"Retrieved sources: {found_sources}")

            except Exception as exc:
                result = {
                    **item,
                    "model": MODEL,
                    "top_k": args.top_k,
                    "chunk_size": args.chunk_size,
                    "overlap": args.overlap,
                    "retrieval_hit": retrieval_hit,
                    "retrieved_chunks": retrieved,
                    "retrieved_sources": found_sources,
                    "status": "error",
                    "model_answer": None,
                    "references": [],
                    "manual_review": "pending",
                    "error": str(exc),
                }

                errors += 1
                print(f"ERROR: {exc}")

            output.write(json.dumps(result, ensure_ascii=False) + "\n")
            output.flush()

    print("\nEvaluation finished.")
    print(f"Successful questions: {completed}")
    print(f"Errors: {errors}")
    print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Evaluate the BakeFix RAG pipeline."
    )

    parser.add_argument(
        "--dataset",
        choices=["baking", "kestrel"],
        required=True,
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--chunk-size", type=int, default=800)
    parser.add_argument("--overlap", type=int, default=80)
    parser.add_argument("--max-distance", type=float, default=None)
    parser.add_argument("--limit", type=int, default=None)

    arguments = parser.parse_args()

    if arguments.top_k < 1:
        parser.error("--top-k must be at least 1")

    if (
        arguments.chunk_size < 1
        or arguments.overlap < 0
        or arguments.overlap >= arguments.chunk_size
    ):
        parser.error("Invalid chunk size or overlap")

    if arguments.limit is not None and arguments.limit < 1:
        parser.error("--limit must be at least 1")

    evaluate(arguments)
