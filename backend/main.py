import os
import json
from typing import Optional, List, AsyncGenerator

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from openai import OpenAI, OpenAIError, AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Modern AI Stack API",
    description="FastAPI backend with SSE streaming + optional RAG (Chroma)",
    version="1.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sync client kept for non-streaming / ingest paths
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
# Async client for streaming
async_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# --- Optional Chroma client (lazy) ---
_chroma_client = None
_collection = None

def get_chroma():
    """Connect to Chroma running in Docker (or local). Returns (client, collection) or (None, None)."""
    global _chroma_client, _collection
    if _collection is not None:
        return _chroma_client, _collection
    try:
        import chromadb

        host = os.getenv("CHROMA_HOST", "localhost")
        port = int(os.getenv("CHROMA_PORT", "8001"))

        # Inside docker-compose the service name is "chroma" and listens on 8000
        if host == "chroma":
            port = 8000

        _chroma_client = chromadb.HttpClient(host=host, port=port)
        _collection = _chroma_client.get_or_create_collection(
            name="docs",
            metadata={"hnsw:space": "cosine"},
        )
        return _chroma_client, _collection
    except Exception as e:
        print(f"[Chroma] not available: {e}")
        return None, None


def build_user_content(prompt: str, use_rag: bool) -> tuple[str, bool]:
    """Optionally augment the prompt with retrieved context."""
    context_used = False
    user_content = prompt

    if use_rag:
        _, collection = get_chroma()
        if collection is not None:
            try:
                results = collection.query(
                    query_texts=[prompt],
                    n_results=min(4, max(1, collection.count() or 1)),
                )
                docs = results.get("documents", [[]])[0]
                if docs:
                    context = "\n\n---\n\n".join(docs)
                    user_content = (
                        "Use the following context to answer the question. "
                        "If the context is insufficient, say so.\n\n"
                        f"Context:\n{context}\n\nQuestion: {prompt}"
                    )
                    context_used = True
            except Exception as e:
                print(f"[RAG] query failed: {e}")

    return user_content, context_used


class QueryRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=8000)
    system: Optional[str] = Field(
        default="You are a helpful AI assistant built on a modern custom stack.",
        max_length=2000,
    )
    use_rag: bool = Field(default=False, description="Retrieve relevant context from the vector store")


class QueryResponse(BaseModel):
    reply: str
    model: str
    context_used: bool = False


@app.get("/health")
async def health():
    _, collection = get_chroma()
    chroma_ok = collection is not None
    return {
        "status": "ok",
        "model": MODEL,
        "chroma": "connected" if chroma_ok else "unavailable",
        "streaming": True,
    }


# ---------- Non-streaming (kept for compatibility / Swagger) ----------
@app.post("/api/generate", response_model=QueryResponse)
async def generate_text(request: QueryRequest):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured")

    user_content, context_used = build_user_content(request.prompt, request.use_rag)

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": request.system},
                {"role": "user", "content": user_content},
            ],
            temperature=0.7,
        )
        content = response.choices[0].message.content or ""
        return QueryResponse(reply=content, model=MODEL, context_used=context_used)
    except OpenAIError as e:
        raise HTTPException(status_code=502, detail=f"OpenAI error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- SSE Streaming ----------
async def event_generator(request: QueryRequest) -> AsyncGenerator[str, None]:
    """Yield Server-Sent Events as the model generates tokens."""
    if not os.getenv("OPENAI_API_KEY"):
        yield f"data: {json.dumps({'error': 'OPENAI_API_KEY is not configured'})}\n\n"
        return

    user_content, context_used = build_user_content(request.prompt, request.use_rag)

    # First event: metadata
    yield f"data: {json.dumps({'type': 'meta', 'model': MODEL, 'context_used': context_used})}\n\n"

    try:
        stream = await async_client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": request.system},
                {"role": "user", "content": user_content},
            ],
            temperature=0.7,
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                # Each token as its own SSE event
                yield f"data: {json.dumps({'type': 'token', 'content': delta.content})}\n\n"

        # Done signal
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except OpenAIError as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


@app.post("/api/generate/stream")
async def generate_stream(request: QueryRequest):
    """Stream tokens via Server-Sent Events (text/event-stream)."""
    return StreamingResponse(
        event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx buffering if present
        },
    )


# ---------- Ingest endpoints ----------
@app.post("/api/ingest")
async def ingest_text(texts: List[str]):
    """Ingest plain text chunks into the vector store."""
    _, collection = get_chroma()
    if collection is None:
        raise HTTPException(status_code=503, detail="Chroma is not available")

    if not texts:
        raise HTTPException(status_code=400, detail="No texts provided")

    ids = [f"doc_{collection.count() + i}" for i in range(len(texts))]
    collection.add(documents=texts, ids=ids)
    return {"ingested": len(texts), "total_docs": collection.count()}


@app.post("/api/ingest-file")
async def ingest_file(file: UploadFile = File(...)):
    """Ingest a plain-text or markdown file."""
    _, collection = get_chroma()
    if collection is None:
        raise HTTPException(status_code=503, detail="Chroma is not available")

    content = (await file.read()).decode("utf-8", errors="ignore")
    chunks = [c.strip() for c in content.split("\n\n") if c.strip()]
    if not chunks:
        chunks = [content[:4000]] if content.strip() else []

    if not chunks:
        raise HTTPException(status_code=400, detail="Empty file")

    ids = [f"file_{file.filename}_{collection.count() + i}" for i in range(len(chunks))]
    collection.add(documents=chunks, ids=ids)
    return {
        "filename": file.filename,
        "chunks": len(chunks),
        "total_docs": collection.count(),
    }


@app.get("/api/docs-count")
async def docs_count():
    _, collection = get_chroma()
    if collection is None:
        return {"count": 0, "chroma": "unavailable"}
    return {"count": collection.count(), "chroma": "connected"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
