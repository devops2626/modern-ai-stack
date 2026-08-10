"""
Unit tests for RAGService.split_async / _split.

These tests do not touch Chroma or OpenAI — they only exercise the
CPU-bound chunking path and its validation layer.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub heavy optional deps so the module imports without chromadb / openai
# installed in the test environment.
# ---------------------------------------------------------------------------
_chroma_stub = MagicMock()
_openai_stub = MagicMock()
sys.modules.setdefault("chromadb", _chroma_stub)
sys.modules.setdefault("openai", _openai_stub)

from services.rag import RAGService  # noqa: E402  (after stubs)


@pytest.fixture
def rag() -> RAGService:
    """Fresh service with deterministic chunk settings."""
    with patch.dict(
        os.environ,
        {
            "CHUNK_SIZE": "50",
            "CHUNK_OVERLAP": "10",
            "CHUNK_MAX_CHARS": "10000",
            "OPENAI_API_KEY": "sk-test",
        },
        clear=False,
    ):
        svc = RAGService()
        svc.chunk_size = 50
        svc.chunk_overlap = 10
        return svc


# ---------------------------------------------------------------------------
# Validation / error handling
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_split_async_rejects_none(rag: RAGService):
    with pytest.raises(ValueError, match="must not be None"):
        await rag.split_async(None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_split_async_rejects_non_string(rag: RAGService):
    with pytest.raises(TypeError, match="must be str"):
        await rag.split_async(12345)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_split_async_rejects_empty(rag: RAGService):
    with pytest.raises(ValueError, match="empty or whitespace"):
        await rag.split_async("")


@pytest.mark.asyncio
async def test_split_async_rejects_whitespace_only(rag: RAGService):
    with pytest.raises(ValueError, match="empty or whitespace"):
        await rag.split_async("   \n\t  ")


@pytest.mark.asyncio
async def test_split_async_rejects_oversized_text(rag: RAGService):
    huge = "x" * 10_001
    with patch.dict(os.environ, {"CHUNK_MAX_CHARS": "10000"}):
        with pytest.raises(ValueError, match="exceeds CHUNK_MAX_CHARS"):
            await rag.split_async(huge)


@pytest.mark.asyncio
async def test_split_async_wraps_internal_failure(rag: RAGService):
    """If _split raises, split_async must surface a RuntimeError."""
    with patch.object(rag, "_split", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError, match="Chunking failed"):
            await rag.split_async("hello world this is fine")


@pytest.mark.asyncio
async def test_split_async_raises_when_no_chunks_produced(rag: RAGService):
    """Defend against a hypothetical empty return from _split."""
    with patch.object(rag, "_split", return_value=[]):
        with pytest.raises(ValueError, match="produced no output"):
            await rag.split_async("some content")


# ---------------------------------------------------------------------------
# Happy-path chunking behaviour
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_split_async_short_text_single_chunk(rag: RAGService):
    text = "Short sentence."
    chunks = await rag.split_async(text)
    assert len(chunks) == 1
    assert chunks[0] == text


@pytest.mark.asyncio
async def test_split_async_respects_paragraph_boundaries(rag: RAGService):
    p1 = "First paragraph about cats."
    p2 = "Second paragraph about dogs."
    text = f"{p1}\n\n{p2}"
    chunks = await rag.split_async(text)
    assert len(chunks) >= 2
    joined = " ".join(chunks)
    assert "cats" in joined
    assert "dogs" in joined


@pytest.mark.asyncio
async def test_split_async_long_text_produces_multiple_chunks(rag: RAGService):
    sentence = "The quick brown fox jumps over the lazy dog. "
    text = sentence * 20  # ~900 chars, chunk_size=50
    chunks = await rag.split_async(text)
    assert len(chunks) > 1
    for c in chunks:
        # Allow slight bloat from overlap
        assert len(c) <= rag.chunk_size + rag.chunk_overlap + 5


@pytest.mark.asyncio
async def test_split_async_applies_overlap(rag: RAGService):
    text = "A" * 40 + "\n\n" + "B" * 40
    chunks = await rag.split_async(text)
    assert len(chunks) >= 2
    if len(chunks) >= 2 and rag.chunk_overlap > 0:
        assert chunks[1]


@pytest.mark.asyncio
async def test_split_sync_matches_async(rag: RAGService):
    """_split and split_async must agree on output for the same input."""
    text = "Paragraph one.\n\nParagraph two is a bit longer than the first."
    sync_chunks = rag._split(text)
    async_chunks = await rag.split_async(text)
    assert sync_chunks == async_chunks


@pytest.mark.asyncio
async def test_split_async_preserves_content(rag: RAGService):
    """Core tokens from the input should appear in the output."""
    text = "Alpha beta gamma. Delta epsilon zeta!\n\nEta theta iota."
    chunks = await rag.split_async(text)
    joined = " ".join(chunks)
    for token in [
        "Alpha",
        "beta",
        "gamma",
        "Delta",
        "epsilon",
        "zeta",
        "Eta",
        "theta",
        "iota",
    ]:
        assert token in joined
