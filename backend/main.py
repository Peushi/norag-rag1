from __future__ import annotations

from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, UploadFile
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
    retrieve_chunks,
    update_settings as update_rag_settings,
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
    SettingsRequest,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT_DIR / "frontend"
FRONTEND_DIST_DIR = FRONTEND_DIR / "dist"
FRONTEND_ASSETS_DIR = FRONTEND_DIST_DIR / "assets"

app = FastAPI(title="BakeFix RAG API")


# ERROR HANDLERS
# what HTTP response FastAPI sends when an error occurs
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=APIErrorResponse(
            error=APIErrorDetail(code="VALIDATION_ERROR", message="Request validation failed.", retryable=False)
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
        chunks = retrieve_chunks(
            question=payload.question,
            document_ids=payload.document_ids,
            top_k=payload.top_k,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RetrieveResponse(chunks=chunks)



# full question - answer route
# retreives relevant chunks and passes them
@app.post("/api/ask", response_model=AskResponse)
async def ask_endpoint(payload: AskRequest):
    try:
        result = ask_question(
            question=payload.question,
            document_ids=payload.document_ids,
            top_k=payload.top_k,
        )
    except LLMServiceUnavailable:
        raise
    except LLMResponseError:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result



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
