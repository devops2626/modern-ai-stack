# Modern AI Stack

Production-oriented blueprint for an end-to-end AI application with **real-time SSE streaming**, **document RAG**, and a polished dark UI.

```
┌─────────────┐     ┌──────────────────────────┐     ┌─────────────┐
│  Next.js 15 │────▶│  FastAPI + RAG service   │────▶│  ChromaDB   │
│  (dark UI)  │◀────│  OpenAI-compatible SSE   │◀────│  (vector)   │
└─────────────┘     └──────────────────────────┘     └─────────────┘
```

## Features

| Feature | Details |
|---------|---------|
| **SSE streaming** | `POST /api/generate/stream` → `text/event-stream` (`meta` → `token`* → `done`) |
| **RAG** | Recursive-style chunking + OpenAI embeddings + Chroma cosine retrieval + source citations |
| **Document upload** | Drag-and-drop or click · `.txt` `.md` `.csv` `.json` + source code |
| **Chat history** | Last turns sent to the model for multi-turn conversations |
| **Multi-provider** | Any OpenAI-compatible endpoint (`OPENAI_BASE_URL`) |
| **Docker Compose** | Backend + Frontend + Chroma with healthchecks & persistent volume |

## Quick Start

```bash
cp backend/.env.example backend/.env   # set OPENAI_API_KEY
docker compose up --build
```

| Service  | URL                        |
|----------|----------------------------|
| Frontend | http://localhost:3000      |
| Backend  | http://localhost:8000      |
| API docs | http://localhost:8000/docs |
| Chroma   | http://localhost:8001      |

### Use

1. Open the frontend  
2. Click **Upload** → drop a document  
3. Toggle **RAG** (auto-enabled after upload)  
4. Ask questions — context is retrieved and cited with `[n]` markers  

## Architecture

- **Layer 1 – Foundation**: OpenAI-compatible LLM + embeddings  
- **Layer 2 – Infrastructure**: FastAPI, Docker, healthchecks  
- **Layer 3 – Integration**: Chroma vector store + modular `services/rag.py`  
- **Layer 4 – Application**: Next.js 15 App Router, React 19, Tailwind, SSE client  

### Backend endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Status + model + doc count |
| GET | `/api/docs-count` | Vector store size |
| POST | `/api/generate` | Non-streaming chat |
| POST | `/api/generate/stream` | SSE streaming chat |
| POST | `/api/ingest` | Ingest text array |
| POST | `/api/ingest-file` | Multipart file upload |
| DELETE | `/api/kb` | Reset knowledge base |

### Example – stream

```bash
curl -N -X POST http://localhost:8000/api/generate/stream \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is this project?", "use_rag": true}'
```

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | **Required** |
| `OPENAI_BASE_URL` | OpenAI | Any compatible endpoint |
| `OPENAI_MODEL` | `gpt-4o-mini` | Chat model |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | 800 / 120 | Text splitter |
| `CHROMA_HOST` / `CHROMA_PORT` | `localhost` / `8001` | Vector DB |

## Project structure

```
modern-ai-stack/
├── docker-compose.yml          # backend + frontend + chroma
├── backend/
│   ├── main.py                 # FastAPI routes + SSE
│   ├── services/
│   │   └── rag.py              # Chunking, embeddings, retrieval
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/app/page.tsx        # Dark chat UI + SSE client
│   ├── package.json            # next@^15.5.21 (patched)
│   └── Dockerfile
└── README.md
```

## Local development (no Docker)

```bash
# Backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # OPENAI_API_KEY=...
# Start Chroma separately or point CHROMA_HOST at a running instance
uvicorn main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev
```

## Security notes

- `.env` is gitignored — never commit API keys.  
- Next.js is on a patched release (≥ 15.5.21) for CVE-2026-44578.  
- Tighten CORS and add auth / rate-limits before production.  

### Rebuild after dependency bumps

```bash
docker compose down && docker compose build --no-cache frontend && docker compose up
```

## Roadmap ideas

- PDF / Office support (`unstructured` / `pypdf`)  
- Multi-model router (OpenAI / Anthropic / Gemini)  
- PostgreSQL chat history  
- GitHub Actions CI  
- Multi-stage production images  

## License

MIT
