"""
Shared fixtures for unit + integration tests.

External services (Chroma, OpenAI) are mocked so the suite runs offline.
"""

from __future__ import annotations

import os
import sys
from typing import Any, AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Stub heavy deps before any app import
sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("openai", MagicMock())

os.environ.setdefault("OPENAI_API_KEY", "sk-test-integration")
os.environ.setdefault("OPENAI_MODEL", "gpt-4o-mini")


@pytest.fixture
def mock_rag() -> MagicMock:
    """Fully controlled RAGService double."""
    rag = MagicMock()
    rag.available = True
    rag.count.return_value = 3
    rag.build_context.return_value = (
        "[1] (source: demo.txt, relevance: 0.92)\nThe capital of France is Paris."
    )
    rag.retrieve = AsyncMock(
        return_value=[
            {
                "content": "The capital of France is Paris.",
                "metadata": {"source": "demo.txt"},
                "score": 0.92,
            }
        ]
    )
    rag.ingest = AsyncMock(
        return_value={"source": "demo.txt", "chunks": 2, "total_docs": 5}
    )
    rag.reset = MagicMock()
    return rag


@pytest.fixture
def client(mock_rag: MagicMock) -> Generator:
    """
    FastAPI TestClient with RAG + OpenAI clients patched.

    Usage::

        def test_health(client):
            r = client.get("/health")
            assert r.status_code == 200
    """
    from fastapi.testclient import TestClient

    # Import app after stubs are in place
    import main

    # Non-streaming chat completion mock
    mock_msg = MagicMock()
    mock_msg.content = "Paris is the capital of France."
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]

    async def _fake_stream(*_a: Any, **_kw: Any) -> AsyncGenerator[Any, None]:
        for token in ["Paris ", "is ", "the capital."]:
            delta = MagicMock()
            delta.content = token
            choice = MagicMock()
            choice.delta = delta
            chunk = MagicMock()
            chunk.choices = [choice]
            yield chunk

    with (
        patch.object(main, "get_rag", return_value=mock_rag),
        patch.object(main, "client") as sync_openai,
        patch.object(main, "async_client") as async_openai,
    ):
        sync_openai.chat.completions.create.return_value = mock_resp
        async_openai.chat.completions.create = AsyncMock(side_effect=_fake_stream)

        with TestClient(main.app) as c:
            yield c
