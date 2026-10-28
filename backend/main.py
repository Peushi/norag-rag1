from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.rag_service import APP_SETTINGS, ask_question, delete_document, get_chunk_by_id, index_all_documents, list_documents, read_text_document, retrieve_chunks
from backend.schemas import APIErrorDetail, APIErrorResponse, AskRequest, AskResponse, ChunkResponse, DocumentListResponse, DocumentSummary, RetrieveRequest, RetrieveResponse, SettingsRequest

ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT_DIR / "frontend"

app = FastAPI(title="BakeFix RAG API")


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


@app.get("/")
async def root():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return RedirectResponse(url="/docs")


app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/health")
async def health():
    return {"status": "ok"}


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
    safe_name = file.filename.replace("..", "")
    destination = (ROOT_DIR / "docs" / safe_name)
    destination.parent.mkdir(exist_ok=True)
    content = await file.read()
    destination.write_bytes(content)
    index_all_documents()
    return {"status": "uploaded", "filename": safe_name}


@app.delete("/api/documents/{document_id}")
async def delete_document_endpoint(document_id: str):
    deleted = delete_document(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")
    index_all_documents()
    return {"status": "deleted", "document_id": document_id}


@app.put("/api/settings")
async def update_settings(payload: SettingsRequest):
    APP_SETTINGS.chunk_size = payload.chunk_size
    APP_SETTINGS.overlap = payload.overlap
    APP_SETTINGS.top_k = payload.top_k
    APP_SETTINGS.relevance_threshold = payload.relevance_threshold
    index_all_documents()
    return {
        "chunk_size": APP_SETTINGS.chunk_size,
        "overlap": APP_SETTINGS.overlap,
        "top_k": APP_SETTINGS.top_k,
        "relevance_threshold": APP_SETTINGS.relevance_threshold,
    }


@app.post("/api/retrieve", response_model=RetrieveResponse)
async def retrieve_endpoint(payload: RetrieveRequest):
    chunks = retrieve_chunks(question=payload.question, document_ids=payload.document_ids, top_k=payload.top_k)
    return RetrieveResponse(chunks=chunks)


@app.post("/api/ask", response_model=AskResponse)
async def ask_endpoint(payload: AskRequest):
    result = ask_question(question=payload.question, document_ids=payload.document_ids, top_k=payload.top_k)
    return result


@app.get("/api/chunks/{chunk_id}", response_model=ChunkResponse)
async def chunk_by_id(chunk_id: str):
    chunk = get_chunk_by_id(chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail=f"Chunk '{chunk_id}' not found.")
    return ChunkResponse(chunk=chunk)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
