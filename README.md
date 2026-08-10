# Modern AI Stack

A clean, production-oriented blueprint for building an end-to-end AI application (chat assistant / RAG-ready agent) with **real-time SSE streaming**.

## Architecture (4 Layers)

| Layer | Component | Recommended Tools | Purpose |
|-------|-----------|-------------------|--------|
| 1. Foundation | LLM Provider | OpenAI, Anthropic, Google Gemini | Core intelligence |
| 2. Infrastructure | Backend & Compute | FastAPI, Docker, Vercel/AWS | API, business logic, hosting |
| 3. Integration | Orchestration & Data | LangChain / LlamaIndex, **Chroma** | RAG, memory, tools |
| 4. Application | UI | Next.js, React, Tailwind | Chat UX, **SSE streaming**, feedback |

## Project Structure

```
modern-ai-stack/
├── backend/
│   ├── main.py                 # FastAPI + SSE + RAG
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example
│   └── ...
├── frontend/
│   ├── src/app/page.tsx        # Streaming chat UI
│   ├── package.json
│   ├── Dockerfile
│   └── ...
├── docker-compose.yml          # backend + frontend + Chroma
├── .gitignore
└── README.md
```

## Quick Start (Docker Compose — recommended)

1. Create your backend env file:

```bash
cp backend/.env.example backend/.env
# Edit backend/.env and add your OPENAI_API_KEY
```

2. Start the full stack:

```bash
docker compose up --build
```

| Service   | URL                          |
|-----------|------------------------------|
| Frontend  | http://localhost:3000        |
| Backend   | http://localhost:8000        |
| API docs  | http://localhost:8000/docs   |
| Chroma    | http://localhost:8001        |

Stop with `Ctrl+C` or `docker compose down`.

## Streaming (SSE)

The chat UI uses **Server-Sent Events** by default.

- Endpoint: `POST /api/generate/stream`
- Media type: `text/event-stream`
- Event types:
  - `meta` — model name + whether RAG context was used
  - `token` — individual generated tokens
  - `done` — stream finished
  - `error` — something went wrong

The classic non-streaming endpoint `POST /api/generate` is still available for scripts / Swagger testing.

Example (curl):

```bash
curl -N -X POST http://localhost:8000/api/generate/stream \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Write a short poem about Docker.", "use_rag": false}'
```

## RAG / Document Q&A

### Ingest

```bash
# Text chunks
curl -X POST http://localhost:8000/api/ingest \
  -H "Content-Type: application/json" \
  -d '["The capital of Morocco is Rabat.", "Casablanca is the largest city."]'

# File upload
curl -X POST http://localhost:8000/api/ingest-file \
  -F "file=@./my-notes.md"
```

### Ask with RAG (streaming)

Toggle **Use RAG** in the UI, or:

```bash
curl -N -X POST http://localhost:8000/api/generate/stream \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is the capital of Morocco?", "use_rag": true}'
```

```bash
curl http://localhost:8000/api/docs-count
```

## Manual setup (without Docker)

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add OPENAI_API_KEY
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install && npm run dev
```

## Security notes

- `.env` files are already in `.gitignore` — never commit API keys.
- In production, tighten CORS origins and add authentication / rate limiting.

## Next steps

- Document upload dropzone in the UI
- Multi-model router (OpenAI / Anthropic / Gemini)
- PostgreSQL + persistent chat history
- CI/CD (GitHub Actions)
- Multi-stage production Dockerfiles

## License

MIT
