# Modern AI Stack

A clean, production-oriented blueprint for building an end-to-end AI application (chat assistant / RAG-ready agent).

## Architecture (4 Layers)

| Layer | Component | Recommended Tools | Purpose |
|-------|-----------|-------------------|--------|
| 1. Foundation | LLM Provider | OpenAI, Anthropic, Google Gemini | Core intelligence |
| 2. Infrastructure | Backend & Compute | FastAPI, Docker, Vercel/AWS | API, business logic, hosting |
| 3. Integration | Orchestration & Data | LangChain / LlamaIndex, Chroma / Postgres | RAG, memory, tools |
| 4. Application | UI | Next.js, React, Tailwind | Chat UX, streaming, feedback |

## Project Structure

```
modern-ai-stack/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example
│   └── services/          # (extend with RAG, agents, etc.)
├── frontend/
│   ├── src/app/page.tsx
│   ├── package.json
│   ├── Dockerfile
│   └── ...
├── docker-compose.yml
├── .gitignore
└── README.md
```

## Quick Start

### Option A — Docker Compose (recommended)

1. Create your backend env file:

```bash
cp backend/.env.example backend/.env
# Edit backend/.env and add your OPENAI_API_KEY
```

2. Start everything:

```bash
docker compose up --build
```

- Frontend: http://localhost:3000  
- Backend API: http://localhost:8000  
- API docs: http://localhost:8000/docs  

Stop with `Ctrl+C` or `docker compose down`.

> The backend mounts the local `./backend` folder so code changes are reflected (uvicorn `--reload`).  
> Frontend also mounts the source for hot reload.

### Option B — Manual (without Docker)

#### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env        # add your OPENAI_API_KEY
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`

## Features in this improved version

- Clean FastAPI backend with CORS, Pydantic models, proper error handling
- OpenAI `gpt-4o-mini` (easy to swap)
- Next.js + Tailwind chat UI with loading states and basic conversation history
- **Docker Compose** for one-command local development
- Ready for RAG (add Chroma / Pinecone + document ingestion)
- Environment variable safety (`.env.example`)
- Git-friendly structure and ignore rules

## Next Steps (Production)

- **RAG**: Ingest PDFs / docs into a vector store and retrieve context before calling the LLM
- **Agents**: LangGraph or CrewAI for multi-step tool use
- **Streaming**: Switch to Server-Sent Events / streaming responses
- **Guardrails**: Structured output + validation (Pydantic / NeMo)
- **Auth & Rate limiting**: Add JWT / API keys and rate limits
- **Deployment**: Use the included Dockerfiles; deploy frontend to Vercel, backend to Railway/Fly/AWS

## License

MIT
