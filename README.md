# Modern AI Stack

A clean, production-oriented blueprint for building an end-to-end AI application (chat assistant / RAG-ready agent).

## Architecture (4 Layers)

| Layer | Component | Recommended Tools | Purpose |
|-------|-----------|-------------------|--------|
| 1. Foundation | LLM Provider | OpenAI, Anthropic, Google Gemini | Core intelligence |
| 2. Infrastructure | Backend & Compute | FastAPI, Docker, Vercel/AWS | API, business logic, hosting |
| 3. Integration | Orchestration & Data | LangChain / LlamaIndex, **Chroma** | RAG, memory, tools |
| 4. Application | UI | Next.js, React, Tailwind | Chat UX, streaming, feedback |

## Project Structure

```
modern-ai-stack/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example
│   └── ...
├── frontend/
│   ├── src/app/page.tsx
│   ├── package.json
│   ├── Dockerfile
│   └── ...
├── docker-compose.yml      # backend + frontend + Chroma
├── .gitignore
└── README.md
```

## Quick Start (Docker Compose — recommended)

1. Create your backend env file:

```bash
cp backend/.env.example backend/.env
# Edit backend/.env and add your OPENAI_API_KEY
```

2. Start the full stack (API + UI + vector DB):

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

> Source is volume-mounted → hot reload works for both backend and frontend.  
> Chroma data is persisted in a Docker volume (`chroma_data`).

## RAG / Document Q&A

The backend talks to the Chroma container automatically.

### 1. Ingest documents

**Plain text chunks** (Swagger or curl):

```bash
curl -X POST http://localhost:8000/api/ingest \
  -H "Content-Type: application/json" \
  -d '["Your first document paragraph.", "Another relevant chunk of knowledge."]'
```

**Upload a .txt / .md file**:

```bash
curl -X POST http://localhost:8000/api/ingest-file \
  -F "file=@./my-notes.md"
```

### 2. Ask with RAG

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What does the document say about X?", "use_rag": true}'
```

Or use the interactive docs at `/docs` and set `use_rag: true`.

Check how many documents are stored:

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
# Optional: run a local Chroma or point CHROMA_HOST/PORT
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

- Better chunking & embeddings (OpenAI embeddings instead of Chroma defaults)
- Streaming responses (SSE)
- Agents (LangGraph / tool calling)
- Auth, rate limits, observability
- Production deployment (Vercel + Railway/Fly + managed vector DB)

## License

MIT
