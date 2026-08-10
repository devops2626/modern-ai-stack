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
│   ├── .env.example
│   └── services/          # (extend with RAG, agents, etc.)
├── frontend/
│   ├── src/app/page.tsx
│   ├── package.json
│   └── ...
├── .gitignore
└── README.md
```

## Quick Start

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env        # add your OPENAI_API_KEY
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API available at `http://localhost:8000`  
Docs: `http://localhost:8000/docs`

### 2. Frontend

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
- Ready for RAG (add Chroma / Pinecone + document ingestion)
- Environment variable safety (`.env.example`)
- Git-friendly structure and ignore rules

## Next Steps (Production)

- **RAG**: Ingest PDFs / docs into a vector store and retrieve context before calling the LLM
- **Agents**: LangGraph or CrewAI for multi-step tool use
- **Streaming**: Switch to Server-Sent Events / streaming responses
- **Guardrails**: Structured output + validation (Pydantic / NeMo)
- **Auth & Rate limiting**: Add JWT / API keys and rate limits
- **Deployment**: Dockerize backend, deploy frontend to Vercel, backend to Railway/Fly/AWS

## License

MIT
