# BakeFix

BakeFix is a small RAG application with a React frontend and a FastAPI backend.

## Backend setup

Install the Python dependencies from the repository root and provide a Google
Gemini API key in `.env`:

```bash
python -m pip install -r requirements.txt
```

```dotenv
GOOGLE_API_KEY=your_google_api_key
```

The backend indexes `.txt` and `.md` files in `docs/`, uses the local
`all-MiniLM-L6-v2` embedding model with Chroma cosine distance, and persists the
vector index locally in `chroma_db/`. The first index or query may download the
embedding model. Add documents through the API or place source documents in
`docs/`; the index is rebuilt after uploads and on the first query when empty.

## Frontend development

The frontend lives in `frontend/` and uses React with Vite. Start the API and
the frontend development server in separate terminals:

```bash
# Terminal 1 — from the repository root
python -m uvicorn backend.main:app --reload

# Terminal 2
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite (usually `http://localhost:5173`). Requests to
`/api` are proxied to the FastAPI server on port 8000.

## Production frontend

Build the static frontend bundle, then run FastAPI from the repository root:

```bash
cd frontend
npm install
npm run build
cd ..
python -m uvicorn backend.main:app
```

The built frontend is served from FastAPI at `http://localhost:8000/`. The
generated `frontend/dist/` directory is ignored by Git; commit the frontend
source and package lockfile instead.

## Retrieval checks

Rebuild and inspect retrieval results from the repository root:

```bash
python -m backend.retrieval_smoke_test
```

The retrieval evaluation runner expects `evaluation/questions.json`, with each
question containing an `id`, `question`, and `expected_sources` list. An empty
`expected_sources` list marks an unanswerable question, which is excluded from
the retrieval hit-rate calculation.

```bash
python -m backend.evaluation
```
