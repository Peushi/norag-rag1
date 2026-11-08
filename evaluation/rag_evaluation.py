import argparse
import json
import sys
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from backend.chunking import chunk_text
from backend.bm25 import BM25Index, K1, B
from backend.graph_retrieval import retrieve_graph
from backend.documents import PROJECT_ROOT, load_documents
from backend.index_settings import validate_settings
from backend.llm_service import MODEL, generate_answer
from backend.retrieval import make_chunk_id, filter_by_relevance
from backend.retrieval_orchestrator import (
    RetrievalQuery,
    RetrieverOutput,
    orchestrate_retrieval,
)
from evaluation.retrieval_metrics import (
    K_VALUES,
    match_evidence,
    score_at_k,
    summarize_metrics,
)


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
    except chromadb.errors.NotFoundError:
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


def count_document_chunks(documents, chunk_size, overlap):
    return sum(
        len(
            chunk_text(
                document["text"],
                chunk_size=chunk_size,
                overlap=overlap,
            )
        )
        for document in documents
    )


Dataset = Literal["baking", "kestrel"]


def run_evaluation(
    *,
    dataset: Dataset,
    top_k: int = 5,
    chunk_size: int = 800,
    overlap: int = 80,
    max_distance: float | None = None,
    output_path: str | Path,
    limit: int | None = None,
    generate_answers: bool = False,
    retrievers: list[str] | None = None,
    compare_path_context: bool = False,
) -> Path:
    if dataset not in DATASETS:
        raise ValueError(f"Unknown evaluation dataset: {dataset}")

    if type(top_k) is not int or top_k < 1:
        raise ValueError("top_k must be at least 1")

    validate_settings(chunk_size, overlap)

    if max_distance is not None and (
        type(max_distance) not in (int, float)
        or not 0 <= max_distance <= 2
    ):
        raise ValueError("max_distance must be between 0 and 2")

    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("limit must be at least 1")

    if type(generate_answers) is not bool:
        raise ValueError("generate_answers must be a boolean")

    if type(compare_path_context) is not bool:
        raise ValueError("compare_path_context must be a boolean")

    if compare_path_context and not generate_answers:
        raise ValueError(
            "Path as Context comparison requires answer generation"
        )

    selected_retrievers = (
        ["dense"] if retrievers is None else retrievers
    )

    valid_retrievers = {"dense", "bm25", "graph"}

    if (
        not selected_retrievers
        or len(set(selected_retrievers)) != len(selected_retrievers)
        or any(
            retriever not in valid_retrievers
            for retriever in selected_retrievers
        )
    ):
        raise ValueError(
            "retrievers must contain unique supported retriever names"
        )

    if "graph" in selected_retrievers and dataset != "kestrel":
        raise ValueError(
            "Graph retrieval is only available for the kestrel dataset"
        )

    if compare_path_context and "graph" not in selected_retrievers:
        raise ValueError(
            "Path as Context comparison requires graph retrieval"
        )

    if compare_path_context:
        raise ValueError(
            "Path as Context answer comparison is not implemented "
            "in this evaluation runner yet."
        )

    config = DATASETS[dataset]

    questions = load_questions(config["questions"])

    if limit is not None:
        questions = questions[:limit]

    documents = load_documents(config["documents"])

    if not documents:
        raise RuntimeError(
            f"No documents found for dataset: {dataset}"
        )

    if not questions:
        raise ValueError("No evaluation questions found")

    # Validate labels before replacing an index or opening an output file.
    for item in questions:
        match_evidence(
            item,
            [],
            documents,
            chunk_size=chunk_size,
            overlap=overlap,
        )

    print(f"Dataset: {dataset}")
    print(f"Documents: {len(documents)}")
    print(f"Questions: {len(questions)}")
    print(f"Chunk size: {chunk_size}")
    print(f"Overlap: {overlap}")
    print(f"Top K: {top_k}")
    print(f"Retrievers: {', '.join(selected_retrievers)}")
    print(f"Path as Context comparison: {compare_path_context}")
    print(f"Generate answers: {generate_answers}")

    collection = None

    bm25_index = (
        BM25Index(documents, chunk_size, overlap)
        if "bm25" in selected_retrievers
        else None
    )

    if "dense" in selected_retrievers:
        collection, total_chunks = build_isolated_index(
            dataset,
            documents,
            chunk_size,
            overlap,
        )
    elif bm25_index is not None:
        total_chunks = len(bm25_index.chunks)
    else:
        total_chunks = count_document_chunks(
            documents,
            chunk_size,
            overlap,
        )

    print(f"Indexed chunks: {total_chunks}")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    completed = 0
    errors = 0
    results_for_summary = []

    with output_path.open("w", encoding="utf-8") as output:
        for index, item in enumerate(questions, start=1):
            question = item["question"]

            print(
                f"\n[{index}/{len(questions)}] "
                f"{item['id']}: {question}"
            )

            candidate_top_k = max(top_k, max(K_VALUES))

            dense_chunks = []
            retriever_results = {}

            def dense_adapter(query):
                nonlocal dense_chunks

                dense_chunks = retrieve(
                    collection,
                    query.question,
                    query.top_k,
                    max_distance,
                )

                ranked = [
                    {
                        **{
                            key: value
                            for key, value in chunk.items()
                            if key != "distance"
                        },
                        "rank": rank,
                        "retriever": "dense",
                        "score": chunk["distance"],
                        "score_type": "cosine_distance",
                    }
                    for rank, chunk in enumerate(dense_chunks, 1)
                ]

                retriever_results["dense"] = ranked

                return RetrieverOutput(chunks=ranked)

            def bm25_adapter(query):
                ranked = bm25_index.search(
                    query.question,
                    query.top_k,
                )

                retriever_results["bm25"] = ranked

                return RetrieverOutput(chunks=ranked)

            def graph_adapter(query):
                graph_result = retrieve_graph(
                    question=query.question,
                    top_k=query.top_k,
                    selected_documents=(
                        list(query.document_ids)
                        if query.document_ids is not None
                        else None
                    ),
                )

                ranked = graph_result["chunks"]

                retriever_results["graph"] = ranked

                return RetrieverOutput(
                    chunks=ranked,
                    graph_paths=graph_result["paths"],
                )

            # Use the shared orchestrator and its RRF implementation.
            adapters = {
                "dense": dense_adapter,
                "bm25": bm25_adapter,
                "graph": graph_adapter,
            }

            retrieval = orchestrate_retrieval(
                RetrievalQuery(
                    question,
                    dataset,
                    candidate_top_k,
                    chunk_size=chunk_size,
                    overlap=overlap,
                ),
                selected_retrievers,
                adapters,
                final_top_k=candidate_top_k,
            )

            distances = {
                chunk["id"]: chunk["distance"]
                for chunk in dense_chunks
            }

            if selected_retrievers == ["dense"]:
                evaluation_chunks = dense_chunks
            else:
                evaluation_chunks = [
                    {
                        **chunk,
                        "distance": distances.get(chunk["id"]),
                    }
                    for chunk in retrieval.chunks
                ]

            # Preserve the configured generation context and legacy output.
            retrieved = evaluation_chunks[:top_k]

            expected_sources = sorted({
                evidence["source"]
                for evidence in item.get("evidence", [])
            })

            found_sources = sorted({
                chunk["source"]
                for chunk in retrieved
            })

            retrieval_hit = (
                bool(set(expected_sources) & set(found_sources))
                if expected_sources
                else None
            )

            evidence_matches = match_evidence(
                item,
                evaluation_chunks,
                documents,
                chunk_size=chunk_size,
                overlap=overlap,
            )

            try:
                response = (
                    generate_answer(question, retrieved)
                    if generate_answers
                    else None
                )

                result = {
                    **item,
                    "model": MODEL if generate_answers else None,
                    "top_k": top_k,
                    "chunk_size": chunk_size,
                    "overlap": overlap,
                    "retrievers": selected_retrievers,
                    "retrieval_hit": retrieval_hit,
                    "retrieved_chunks": retrieved,
                    "retrieved_sources": found_sources,
                    "status": (
                        response.status
                        if response
                        else "retrieval_only"
                    ),
                    "model_answer": (
                        response.answer if response else None
                    ),
                    "references": [
                        reference.model_dump()
                        for reference in (
                            response.references if response else []
                        )
                    ],
                    "manual_review": "pending",
                    "error": None,
                }

                completed += 1

                print(f"Status: {result['status']}")
                print(f"Retrieved sources: {found_sources}")

            except Exception as exc:
                result = {
                    **item,
                    "model": MODEL if generate_answers else None,
                    "top_k": top_k,
                    "chunk_size": chunk_size,
                    "overlap": overlap,
                    "retrievers": selected_retrievers,
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

            # Keep the existing source-based retrieval_hit for compatibility.
            result["evidence_matches"] = evidence_matches
            result["generate_answers"] = generate_answers
            result["compare_path_context"] = compare_path_context
            result["retrieval_metrics"] = score_at_k(evidence_matches)
            result["evaluation_chunks"] = evaluation_chunks
            result["retriever_results"] = retriever_results
            result["fused_chunks"] = retrieval.chunks

            result["evaluation_config"] = {
                "dataset": dataset,
                "retrievers": selected_retrievers,
                "compare_path_context": compare_path_context,
                "configuration_id": (
                    f"{'_'.join(selected_retrievers)}_minilm_"
                    f"{chunk_size}_{overlap}"
                ),
                "embedding_model": "all-MiniLM-L6-v2",
                "distance_metric": "cosine",
                "k_values": list(K_VALUES),
                "max_distance": max_distance,
                "limit": limit,
                "candidate_top_k": candidate_top_k,
                "bm25_parameters": (
                    {"k1": K1, "b": B}
                    if bm25_index is not None
                    else None
                ),
                "fusion": "RRF k=60; equal weights; ties by chunk ID",
                "threshold_scope": "dense candidates only",
            }

            results_for_summary.append(result)

            output.write(
                json.dumps(result, ensure_ascii=False) + "\n"
            )
            output.flush()

    summary = {
        "dataset": dataset,
        "retrievers": selected_retrievers,
        "compare_path_context": compare_path_context,
        "generate_answers": generate_answers,
        "chunk_size": chunk_size,
        "overlap": overlap,
        "top_k": top_k,
        "max_distance": max_distance,
        "limit": limit,
        "embedding_model": "all-MiniLM-L6-v2",
        "distance_metric": "cosine",
        "configuration_id": (
            f"{'_'.join(selected_retrievers)}_minilm_"
            f"{chunk_size}_{overlap}"
        ),
        "candidate_top_k": max(top_k, max(K_VALUES)),
        "bm25_parameters": (
            {"k1": K1, "b": B}
            if bm25_index is not None
            else None
        ),
        "fusion": "RRF k=60; equal weights; ties by chunk ID",
        "threshold_scope": "dense candidates only",
        "indexed_documents": len(documents),
        "indexed_chunks": total_chunks,
        "k_values": list(K_VALUES),
        "recall_averaging": (
            "macro: mean of per-question evidence recall"
        ),
        "relevance_rule": (
            "expected source and full quote in one chunk; "
            "whitespace normalized"
        ),
        **summarize_metrics(results_for_summary),
    }

    summary_path = output_path.with_name(
        output_path.stem + "_summary.jsonl"
    )

    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    for k, metrics in summary["overall"]["metrics"].items():
        print(f"k={k}: {metrics}")

    print(f"Summary saved to: {summary_path}")
    print("\nEvaluation finished.")
    print(f"Successful questions: {completed}")
    print(f"Errors: {errors}")
    print(f"Results saved to: {output_path}")

    return output_path


def evaluate(args, output_path=None):
    """CLI compatibility wrapper around the reusable evaluation function."""

    if output_path is None:
        mode = (
            "rag"
            if getattr(args, "generate_answers", False)
            else "retrieval"
        )

        suffix = ""
        selected = getattr(args, "retrievers", ["dense"])

        if selected != ["dense"]:
            suffix += "_" + "_".join(sorted(selected))

        if args.top_k != 5:
            suffix += f"_k{args.top_k}"

        if args.max_distance is not None:
            suffix += f"_distance{args.max_distance}"

        if args.limit is not None:
            suffix += f"_limit{args.limit}"

        output_path = (
            EVALUATION_DIR
            / "results"
            / (
                f"{args.dataset}_{mode}_"
                f"{args.chunk_size}_{args.overlap}{suffix}.jsonl"
            )
        )

    return run_evaluation(
        dataset=args.dataset,
        top_k=args.top_k,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        max_distance=args.max_distance,
        output_path=output_path,
        limit=args.limit,
        generate_answers=getattr(args, "generate_answers", False),
        retrievers=getattr(args, "retrievers", ["dense"]),
        compare_path_context=getattr(
            args,
            "compare_path_context",
            False,
        ),
    )


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

    parser.add_argument(
        "--generate-answers",
        action="store_true",
        help="Also call Gemini; default is retrieval only",
    )

    parser.add_argument(
        "--retrievers",
        nargs="+",
        choices=["dense", "bm25", "graph"],
        default=["dense"],
    )

    parser.add_argument(
        "--compare-path-context",
        action="store_true",
        help="Compare generated answers with and without Graph Path as Context",
    )

    parser.add_argument(
        "--output",
        "--output-path",
        dest="output",
        type=Path,
        default=None,
        help="Results JSONL path",
    )

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

    evaluate(arguments, output_path=arguments.output)
