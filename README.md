# Modern AI Stack

A clean, production-oriented blueprint for building an end-to-end AI application (chat assistant / RAG-ready agent) with **real-time SSE streaming** and **document upload**.

## Architecture (4 Layers)

| Layer | Component | Recommended Tools | Purpose |
|-------|-----------|-------------------|--------|
| 1. Foundation | LLM Provider | OpenAI, Anthropic, Google Gemini | Core intelligence |
| 2. Infrastructure | Backend & Compute | FastAPI, Docker, Vercel/AWS | API, business logic, hosting |
| 3. Integration | Orchestration & Data | **Chroma** vector store | RAG, memory, tools |
| 4. Application | UI | Next.js 15, React 19, Tailwind | Chat UX, SSE streaming, **doc upload** |

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

## Security: Next.js upgrade (CVE-2026-44578)

The frontend was upgraded from Next.js 14 → **15.5.21+** to fix a high-severity SSRF in WebSocket upgrade handling.

### Dockerfile update / rebuild steps

After any security bump to `frontend/package.json`, force a clean image rebuild so the new `next` version is installed inside the container:

```bash
# 1. Stop running stack
docker compose down

# 2. Remove the old frontend image (optional but recommended)
docker compose build --no-cache frontend

# 3. Start everything again
docker compose up --build
```

Or as a one-liner:

```bash
docker compose down && docker compose build --no-cache frontend && docker compose up
```

**Why `--no-cache`?**  
The frontend volume mounts `./frontend` over `/app`, but `node_modules` is an anonymous volume (`/app/node_modules`). A normal rebuild can reuse a cached layer that still has the old Next.js. `--no-cache` guarantees `npm install` runs against the updated `package.json`.

### Verify the patched version is running

```bash
# Inside the running frontend container
docker compose exec frontend npm list next
# Expect: next@15.5.x (or higher)
```

### Manual (non-Docker) upgrade steps

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install          # pulls next@^15.5.21 + react@^19
npm run dev
```

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
│   ├── package.json         # next@^15.5.21 (patched)
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

## Security notes

- `.env` is gitignored — never commit API keys.
- Next.js is on a patched release (≥ 15.5.21) for CVE-2026-44578.
- Tighten CORS and add auth/rate-limits before production.

## Next ideas

- PDF support (PyPDF / unstructured)
- Multi-model router (OpenAI / Anthropic / Gemini)
- PostgreSQL + chat history
- CI/CD (GitHub Actions)
- Multi-stage production Docker images

## License

MIT
