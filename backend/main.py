"""
Modern AI Stack – FastAPI backend
SSE streaming · RAG (Chroma + OpenAI embeddings) · document ingest · chat history
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, AsyncGenerator, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI, OpenAI, OpenAIError
from pydantic import BaseModel, Field

from services.rag import get_rag

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("main")

app = FastAPI(
    title="Modern AI Stack API",
    description="FastAPI + SSE streaming + RAG (Chroma) + document upload",
    version="1.4.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://frontend:3000",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL") or None,
)
async_client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL") or None,
)
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

DEFAULT_SYSTEM = (
    "You are a precise, helpful AI assistant. "
    "When context from the knowledge base is provided, use it and cite sources with [n] markers. "
    "If the context is insufficient, say so and answer from general knowledge."
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class QueryRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=8000)
    system: Optional[str] = Field(default=None, max_length=2000)
    use_rag: bool = Field(default=False)
    history: List[ChatMessage] = Field(default_factory=list)
    k: int = Field(default=4, ge=1, le=12)


class QueryResponse(BaseModel):
    reply: str
    model: str
    context_used: bool = False


# ---------------------------------------------------------------------------
async def build_messages(
    request: QueryRequest,
) -> tuple[list[dict[str, str]], bool]:
    context_used = False
    user_content = request.prompt

    if request.use_rag:
        rag = get_rag()
        docs = await rag.retrieve(request.prompt, k=request.k)
        ctx = rag.build_context(docs)
        if ctx:
            user_content = (
                "Use the following context to answer the question. "
                "Cite sources using the [n] markers when you use them.\n\n"
                f"Context:\n{ctx}\n\n---\n\nQuestion: {request.prompt}"
            )
            context_used = True

    messages: list[dict[str, str]] = [
        {"role": "system", "content": request.system or DEFAULT_SYSTEM},
    ]

    # Keep last ~8 turns
    for msg in request.history[-16:]:
        if msg.role in ("user", "assistant"):
            messages.append({"role": msg.role, "content": msg.content})

    messages.append({"role": "user", "content": user_content})
    return messages, context_used


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    rag = get_rag()
    return {
        "status": "ok",
        "version": "1.4.0",
        "model": MODEL,
        "chroma": "connected" if rag.available else "unavailable",
        "docs": rag.count() if rag.available else 0,
        "streaming": True,
    }


@app.get("/api/docs-count")
async def docs_count():
    rag = get_rag()
    if not rag.available:
        return {"count": 0, "chroma": "unavailable"}
    return {"count": rag.count(), "chroma": "connected"}


@app.post("/api/generate", response_model=QueryResponse)
async def generate_text(request: QueryRequest):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured")

    messages, context_used = await build_messages(request)

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.3,
        )
        content = response.choices[0].message.content or ""
        return QueryResponse(reply=content, model=MODEL, context_used=context_used)
    except OpenAIError as e:
        raise HTTPException(status_code=502, detail=f"OpenAI error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def event_generator(request: QueryRequest) -> AsyncGenerator[str, None]:
    if not os.getenv("OPENAI_API_KEY"):
        yield f"data: {json.dumps({'type': 'error', 'message': 'OPENAI_API_KEY is not configured'})}\n\n"
        return

    messages, context_used = await build_messages(request)

    yield f"data: {json.dumps({'type': 'meta', 'model': MODEL, 'context_used': context_used})}\n\n"

    try:
        stream = await async_client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.3,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield f"data: {json.dumps({'type': 'token', 'content': delta.content})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    except OpenAIError as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


@app.post("/api/generate/stream")
async def generate_stream(request: QueryRequest):
    return StreamingResponse(
        event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/ingest")
async def ingest_text(texts: List[str]):
    rag = get_rag()
    if not rag.available:
        raise HTTPException(status_code=503, detail="Chroma is not available")
    if not texts:
        raise HTTPException(status_code=400, detail="No texts provided")

    total_chunks = 0
    for i, t in enumerate(texts):
        result = await rag.ingest(t, source=f"text_{i}")
        total_chunks += result["chunks"]
    return {"ingested": total_chunks, "total_docs": rag.count()}


@app.post("/api/ingest-file")
async def ingest_file(file: UploadFile = File(...)):
    rag = get_rag()
    if not rag.available:
        raise HTTPException(status_code=503, detail="Chroma is not available")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")

    content = (await file.read()).decode("utf-8", errors="ignore")
    if not content.strip():
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        result = await rag.ingest(content, source=file.filename)
        return {
            "filename": file.filename,
            "chunks": result["chunks"],
            "total_docs": result["total_docs"],
        }
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Ingest failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/kb")
async def reset_kb():
    rag = get_rag()
    if not rag.available:
        raise HTTPException(status_code=503, detail="Chroma is not available")
    rag.reset()
    return {"ok": True, "message": "Knowledge base cleared"}


@app.get("/")
async def root():
    return {
        "name": "Modern AI Stack API",
        "version": "1.4.0",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
