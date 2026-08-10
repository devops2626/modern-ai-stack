# Modern AI Stack

A clean, production-oriented blueprint for building an end-to-end AI application (chat assistant / RAG-ready agent) with **real-time SSE streaming** and **document upload**.

## Architecture (4 Layers)

| Layer | Component | Recommended Tools | Purpose |
|-------|-----------|-------------------|--------|
| 1. Foundation | LLM Provider | OpenAI, Anthropic, Google Gemini | Core intelligence |
| 2. Infrastructure | Backend & Compute | FastAPI, Docker, Vercel/AWS | API, business logic, hosting |
| 3. Integration | Orchestration & Data | **Chroma** vector store | RAG, memory, tools |
| 4. Application | UI | Next.js, React, Tailwind | Chat UX, SSE streaming, **doc upload** |

## Quick Start (Docker Compose)

```bash
cp backend/.env.example backend/.env   # add OPENAI_API_KEY
docker compose up --build
```

| Service   | URL                        |
|-----------|----------------------------|
| Frontend  | http://localhost:3000      |
| Backend   | http://localhost:8000      |
| API docs  | http://localhost:8000/docs |
| Chroma    | http://localhost:8001      |

## Features

### Real-time streaming (SSE)
- `POST /api/generate/stream` → `text/event-stream`
- Events: `meta` → `token`* → `done` (or `error`)
- Classic non-streaming endpoint still available at `/api/generate`

### Document RAG
1. Click **Upload docs** in the header (or use the API).
2. Drop a `.txt` / `.md` / `.csv` / `.json` file (or click to browse).
3. Toggle **Use RAG** — the chat will retrieve relevant chunks and inject them into the prompt before streaming.

Backend endpoints:
- `POST /api/ingest` — JSON array of text chunks
- `POST /api/ingest-file` — multipart file upload
- `GET /api/docs-count` — number of stored chunks

## Project Structure

```
modern-ai-stack/
├── backend/
│   ├── main.py              # FastAPI + SSE + RAG + ingest
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/app/page.tsx     # Streaming chat + upload dropzone
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml       # backend + frontend + Chroma
└── README.md
```

## Manual setup (no Docker)

```bash
# Backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # OPENAI_API_KEY=...
uvicorn main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev
```

## Security

- `.env` is gitignored — never commit API keys.
- Tighten CORS and add auth/rate-limits before production.

## Next ideas

- PDF support (PyPDF / unstructured)
- Multi-model router (OpenAI / Anthropic / Gemini)
- PostgreSQL + chat history
- CI/CD (GitHub Actions)
- Multi-stage production Docker images

## License

MIT
