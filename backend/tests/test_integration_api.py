"""
Integration test examples for the Modern AI Stack API.

These tests hit the full FastAPI request path with Chroma + OpenAI
mocked out (see conftest.py). They document the expected contracts
and can be used as a template for live-stack tests later.

Run::

    cd backend && python -m pytest tests/test_integration_api.py -v
"""

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# =====================================================================
# Health & metadata
# =====================================================================
def test_health_returns_ok(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["streaming"] is True
    assert "model" in body
    assert body["chroma"] == "connected"
    assert body["docs"] == 3


def test_root_lists_endpoints(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Modern AI Stack API"
    assert body["docs"] == "/docs"
    assert body["health"] == "/health"


def test_docs_count(client: TestClient):
    r = client.get("/api/docs-count")
    assert r.status_code == 200
    assert r.json() == {"count": 3, "chroma": "connected"}


# =====================================================================
# Non-streaming chat
# =====================================================================
def test_generate_without_rag(client: TestClient):
    r = client.post(
        "/api/generate",
        json={"prompt": "What is the capital of France?", "use_rag": False},
    )
    assert r.status_code == 200
    body = r.json()
    assert "Paris" in body["reply"]
    assert body["context_used"] is False
    assert body["model"]


def test_generate_with_rag(client: TestClient, mock_rag: MagicMock):
    r = client.post(
        "/api/generate",
        json={"prompt": "What is the capital of France?", "use_rag": True, "k": 3},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["context_used"] is True
    assert "Paris" in body["reply"]
    mock_rag.retrieve.assert_awaited()


def test_generate_with_history(client: TestClient):
    r = client.post(
        "/api/generate",
        json={
            "prompt": "And its population?",
            "use_rag": False,
            "history": [
                {"role": "user", "content": "What is the capital of France?"},
                {"role": "assistant", "content": "Paris."},
            ],
        },
    )
    assert r.status_code == 200
    assert r.json()["reply"]


def test_generate_rejects_empty_prompt(client: TestClient):
    r = client.post("/api/generate", json={"prompt": ""})
    assert r.status_code == 422  # Pydantic validation


# =====================================================================
# SSE streaming chat
# =====================================================================
def test_generate_stream_sse(client: TestClient):
    """Collect SSE events and verify meta → token* → done sequence."""
    with client.stream(
        "POST",
        "/api/generate/stream",
        json={"prompt": "Hello", "use_rag": False},
    ) as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]

        events = []
        for line in r.iter_lines():
            if not line or not line.startswith("data: "):
                continue
            payload = json.loads(line[6:])
            events.append(payload)

    types = [e.get("type") for e in events]
    assert "meta" in types
    assert "token" in types
    assert "done" in types
    assert types[0] == "meta"
    assert types[-1] == "done"

    tokens = "".join(e["content"] for e in events if e.get("type") == "token")
    assert "Paris" in tokens or "capital" in tokens or len(tokens) > 0


# =====================================================================
# Ingest
# =====================================================================
def test_ingest_text(client: TestClient, mock_rag: MagicMock):
    r = client.post("/api/ingest", json=["Chunk A about APIs.", "Chunk B about RAG."])
    assert r.status_code == 200
    body = r.json()
    assert body["ingested"] == 4  # mock returns 2 chunks per call × 2 texts
    assert body["total_docs"] == 3  # from mock_rag.count()
    assert mock_rag.ingest.await_count == 2


def test_ingest_text_empty_list(client: TestClient):
    r = client.post("/api/ingest", json=[])
    assert r.status_code == 400


def test_ingest_file(client: TestClient, mock_rag: MagicMock):
    content = b"# Demo\n\nThe capital of France is Paris.\n"
    r = client.post(
        "/api/ingest-file",
        files={"file": ("demo.md", BytesIO(content), "text/markdown")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["filename"] == "demo.md"
    assert body["chunks"] == 2
    assert body["total_docs"] == 5
    mock_rag.ingest.assert_awaited_once()


def test_ingest_file_empty(client: TestClient):
    r = client.post(
        "/api/ingest-file",
        files={"file": ("empty.txt", BytesIO(b"   "), "text/plain")},
    )
    assert r.status_code == 400


def test_ingest_when_chroma_down(client: TestClient, mock_rag: MagicMock):
    mock_rag.available = False
    r = client.post("/api/ingest", json=["hello"])
    assert r.status_code == 503


# =====================================================================
# Knowledge-base admin
# =====================================================================
def test_reset_kb(client: TestClient, mock_rag: MagicMock):
    r = client.delete("/api/kb")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    mock_rag.reset.assert_called_once()


def test_reset_kb_when_chroma_down(client: TestClient, mock_rag: MagicMock):
    mock_rag.available = False
    r = client.delete("/api/kb")
    assert r.status_code == 503


# =====================================================================
# Live-stack example (skipped unless RUN_LIVE_TESTS=1)
# =====================================================================
@pytest.mark.skipif(
    __import__("os").environ.get("RUN_LIVE_TESTS") != "1",
    reason="Set RUN_LIVE_TESTS=1 and start the stack to run live integration tests",
)
def test_live_health_against_running_stack():
    """
    Example of a true end-to-end check against a running docker-compose stack.

        RUN_LIVE_TESTS=1 pytest tests/test_integration_api.py -k live -v
    """
    import httpx

    r = httpx.get("http://localhost:8000/health", timeout=5.0)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
