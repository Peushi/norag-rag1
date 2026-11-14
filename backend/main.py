
from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from openai import APIConnectionError, APIStatusError, APITimeoutError

from backend.documents import add_document_and_reindex
from backend.evaluation_runs import (
    EvaluationAlreadyRunningError,
    EvaluationRunNotFoundError,
    create_run,
    execute_run,
    get_run,
    get_run_results,
)
from backend.llm_service import LLMResponseError, LLMServiceUnavailable
from backend.rag_service import (
    APP_SETTINGS,
    ask_question,
    delete_document,
    get_chunk_by_id,
    list_documents,
    retrieve_selected_chunks,
    update_settings as update_rag_settings,
)
from backend.retrieval_orchestrator import RetrieverUnavailableError
from backend.retrieval_comparison import (
    RetrievalComparisonDataError,
    RetrievalComparisonNotFoundError,
    get_retrieval_comparison,
)
from backend.schemas import (
    APIErrorDetail,
    APIErrorResponse,
    AskRequest,
    AskResponse,
    ChunkResponse,
    DocumentListResponse,
    DocumentSummary,
    EvaluationResultsResponse,
    EvaluationRunRequest,
    EvaluationRunResponse,
    RetrieveRequest,
    RetrieveResponse,
    RetrievalComparisonResponse,
    SettingsRequest,
    TraceResponse,
    WordChunksResponse,
    WordQuestionAnalysisRequest,
    WordQuestionAnalysisResponse,
    WordQuestionListResponse,
    WordVocabularyResponse,
)
from backend.words_analytics import (
    analyze_question as analyze_words_question,
    get_vocabulary,
    get_word_chunks,
    list_questions,
)
from backend.tracing import create_trace, get_trace

ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT_DIR / "frontend"
FRONTEND_DIST_DIR = FRONTEND_DIR / "dist"
FRONTEND_ASSETS_DIR = FRONTEND_DIST_DIR / "assets"

app = FastAPI(title="BakeFix RAG API")


@app.middleware("http")
async def trace_ask_requests(request: Request, call_next):
    if request.method != "POST" or request.url.path != "/api/ask":
        return await call_next(request)

    trace = create_trace("question")
    request.state.ask_trace = trace
    try:
        response = await call_next(request)
    except Exception:
        trace.finish("failed")
        raise

    trace.finish("failed" if response.status_code >= 400 else "completed")
    response.headers["X-Trace-ID"] = trace.trace_id
    return response


# ERROR HANDLERS
# what HTTP response FastAPI sends when an error occurs
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=APIErrorResponse(
            error=APIErrorDetail(code="VALIDATION_ERROR", message="Requestvalidation failed.", retryable=False)
        ).model_dump(),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    content = APIErrorResponse(
        error=APIErrorDetail(code="HTTP_ERROR", message=exc.detail, retryable=False)
    ).model_dump()
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(LLMServiceUnavailable)
async def llm_unavailable_handler(request: Request, exc: LLMServiceUnavailable):
    return JSONResponse(
        status_code=503,
        content=APIErrorResponse(
            error=APIErrorDetail(
                code="LLM_UNAVAILABLE",
                message=str(exc),
                retryable=True,
            )
        ).model_dump(),
    )


@app.exception_handler(LLMResponseError)
async def llm_response_error_handler(request: Request, exc: LLMResponseError):
    return JSONResponse(
        status_code=502,
        content=APIErrorResponse(
            error=APIErrorDetail(
                code="LLM_INVALID_RESPONSE",
                message=str(exc),
                retryable=False,
            )
        ).model_dump(),
    )


@app.exception_handler(APITimeoutError)
async def upstream_timeout_handler(request: Request, exc: APITimeoutError):
    return JSONResponse(
        status_code=504,
        content=APIErrorResponse(
            error=APIErrorDetail(
                code="LLM_TIMEOUT",
                message="The answer service timed out.",
                retryable=True,
            )
        ).model_dump(),
    )


@app.exception_handler(APIConnectionError)
async def upstream_connection_error_handler(request: Request, exc: APIConnectionError):
    return JSONResponse(
        status_code=503,
        content=APIErrorResponse(
            error=APIErrorDetail(
                code="LLM_UNAVAILABLE",
                message="The answer service is currently unavailable.",
                retryable=True,
            )
        ).model_dump(),
    )


@app.exception_handler(APIStatusError)
async def upstream_status_error_handler(request: Request, exc: APIStatusError):
    return JSONResponse(
        status_code=502,
        content=APIErrorResponse(
            error=APIErrorDetail(
                code="LLM_UPSTREAM_ERROR",
                message="The answer service returned an error.",
                retryable=exc.status_code >= 500,
            )
        ).model_dump(),
    )


@app.get("/")
async def root():
    index_file = FRONTEND_DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return RedirectResponse(url="/docs")


if FRONTEND_ASSETS_DIR.is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=str(FRONTEND_ASSETS_DIR)),
        name="frontend-assets",
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/words", response_model=WordVocabularyResponse)
async def words_vocabulary(
    dataset: Literal["baking", "kestrel"],
    query: str = Query(default="", max_length=100),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    chunk_size: int = Query(default=800, ge=100, le=2000),
    overlap: int = Query(default=80, ge=0, le=1000),
):
    if overlap >= chunk_size:
        raise HTTPException(
            status_code=422,
            detail="overlap must be smaller than chunk_size",
        )
    return get_vocabulary(
        dataset,
        query=query,
        limit=limit,
        offset=offset,
        chunk_size=chunk_size,
        overlap=overlap,
    )


@app.get("/api/words/questions", response_model=WordQuestionListResponse)
async def words_questions(dataset: Literal["baking", "kestrel"]):
    try:
        questions = list_questions(dataset)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"dataset": dataset, "questions": questions}


@app.get("/api/words/{word}/chunks", response_model=WordChunksResponse)
async def words_for_selected_word(
    word: str,
    dataset: Literal["baking", "kestrel"],
    chunk_size: int = Query(default=800, ge=100, le=2000),
    overlap: int = Query(default=80, ge=0, le=1000),
):
    normalized_words = word.casefold()
    if not normalized_words or len(normalized_words.split()) != 1:
        raise HTTPException(status_code=422, detail="Provide exactly one word.")
    if overlap >= chunk_size:
        raise HTTPException(
            status_code=422,
            detail="overlap must be smaller than chunk_size",
        )
    return get_word_chunks(
        dataset,
        normalized_words,
        chunk_size=chunk_size,
        overlap=overlap,
    )


@app.post(
    "/api/words/analyze-question",
    response_model=WordQuestionAnalysisResponse,
)
async def analyze_words_in_question(payload: WordQuestionAnalysisRequest):
    return analyze_words_question(
        payload.dataset,
        payload.question,
        chunk_size=payload.chunk_size,
        overlap=payload.overlap,
    )


@app.post(
    "/api/evaluations",
    response_model=EvaluationRunResponse,
    status_code=202,
)
async def start_evaluation(
    payload: EvaluationRunRequest,
    background_tasks: BackgroundTasks,
):
    try:
        run = create_run(payload)
    except EvaluationAlreadyRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    background_tasks.add_task(execute_run, run.run_id, payload)
    return run


@app.get(
    "/api/evaluations/retrieval/{experiment_id}/results",
    response_model=RetrievalComparisonResponse,
)
async def retrieval_comparison_results(experiment_id: str):
    try:
        return get_retrieval_comparison(experiment_id)
    except RetrievalComparisonNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Retrieval comparison '{experiment_id}' was not found.",
        ) from exc
    except RetrievalComparisonDataError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get(
    "/api/evaluations/{run_id}",
    response_model=EvaluationRunResponse,
)
async def evaluation_status(run_id: str):
    try:
        return get_run(run_id)
    except EvaluationRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Evaluation run not found.") from exc


@app.get(
    "/api/evaluations/{run_id}/results",
    response_model=EvaluationResultsResponse,
)
async def evaluation_results(run_id: str):
    try:
        run = get_run(run_id)
        results = get_run_results(run_id)
    except EvaluationRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Evaluation run not found.") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return EvaluationResultsResponse(
        run_id=run.run_id,
        dataset=run.dataset,
        results=results,
    )


@app.get("/api/documents", response_model=DocumentListResponse)
async def get_documents():
    docs = list_documents()
    return DocumentListResponse(
        documents=[DocumentSummary(id=str(item["id"]), name=str(item["name"]), size_bytes=int(item["size_bytes"])) for item in docs]
    )


@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=422, detail="A file is required.")
    safe_name = Path(file.filename).name
    if Path(safe_name).suffix.lower() not in {".md", ".txt"}:
        raise HTTPException(status_code=422, detail="Only .md and .txt documents are supported.")

    content = await file.read()
    try:
        text = content.decode("utf-8")
        add_document_and_reindex(
            safe_name,
            text,
            chunk_size=APP_SETTINGS.chunk_size,
            overlap=APP_SETTINGS.overlap,
        )
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="Documents must use UTF-8 encoding.") from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "uploaded", "filename": safe_name}


@app.delete("/api/documents/{document_id:path}")
async def delete_document_endpoint(document_id: str):
    try:
        deleted = delete_document(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")
    return {"status": "deleted", "document_id": document_id}


@app.put("/api/settings")
async def update_settings(payload: SettingsRequest):
    stats = update_rag_settings(
        chunk_size=payload.chunk_size,
        overlap=payload.overlap,
        top_k=payload.top_k,
        relevance_threshold=payload.relevance_threshold,
    )
    return {
        "chunk_size": APP_SETTINGS.chunk_size,
        "overlap": APP_SETTINGS.overlap,
        "top_k": APP_SETTINGS.top_k,
        "relevance_threshold": APP_SETTINGS.relevance_threshold,
        "index": stats,
    }


# what the retreival part found
@app.post("/api/retrieve", response_model=RetrieveResponse)
async def retrieve_endpoint(payload: RetrieveRequest):
    try:
        retrieval = retrieve_selected_chunks(
            question=payload.question,
            dataset=payload.dataset,
            retrievers=payload.retrievers,
            document_ids=payload.document_ids,
            top_k=payload.top_k,
        )
    except RetrieverUnavailableError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RetrieveResponse(
        chunks=retrieval.chunks,
        retrievers=list(retrieval.retrievers),
        graph_paths=retrieval.graph_paths,
        graph_supporting_chunks=retrieval.graph_chunks,
    )


# full question - answer route
# retreives relevant chunks and passes them
@app.post("/api/ask", response_model=AskResponse)
async def ask_endpoint(payload: AskRequest, request: Request):
    trace = request.state.ask_trace
    try:
        result = ask_question(
            question=payload.question,
            dataset=payload.dataset,
            retrievers=payload.retrievers,
            document_ids=payload.document_ids,
            top_k=payload.top_k,
            include_path_context=payload.include_path_context,
            trace=trace,
            style=payload.style,
        )
    except RetrieverUnavailableError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except LLMServiceUnavailable:
        raise
    except LLMResponseError:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    trace.set_outcome(result.status)
    return result.model_copy(update={"trace_id": trace.trace_id})


@app.get("/api/traces/{trace_id}", response_model=TraceResponse)
async def trace_endpoint(trace_id: str):
    trace = get_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace not found.")
    return trace


# looks up 1 indexed chunk
@app.get("/api/chunks/{chunk_id:path}", response_model=ChunkResponse)
async def chunk_by_id(chunk_id: str):
    chunk = get_chunk_by_id(chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail=f"Chunk '{chunk_id}' not found.")
    return ChunkResponse(chunk=chunk)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
