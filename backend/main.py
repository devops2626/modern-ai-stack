import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from openai import OpenAI, OpenAIError
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Modern AI Stack API",
    description="Clean FastAPI backend for LLM chat / RAG-ready assistants",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


class QueryRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=8000)
    system: Optional[str] = Field(
        default="You are a helpful AI assistant built on a modern custom stack.",
        max_length=2000,
    )


class QueryResponse(BaseModel):
    reply: str
    model: str


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL}


@app.post("/api/generate", response_model=QueryResponse)
async def generate_text(request: QueryRequest):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured")

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.prompt},
            ],
            temperature=0.7,
        )
        content = response.choices[0].message.content or ""
        return QueryResponse(reply=content, model=MODEL)
    except OpenAIError as e:
        raise HTTPException(status_code=502, detail=f"OpenAI error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
