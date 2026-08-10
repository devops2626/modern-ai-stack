"""
RAG service – Chroma (HTTP) + OpenAI embeddings + async-friendly chunking.

Performance notes
-----------------
* Chunking is pure CPU; we offload it with asyncio.to_thread so the
  FastAPI event loop is never blocked.
* Embeddings use AsyncOpenAI and are sent in batches (default 64).
* Chroma HTTP calls are still sync; we also wrap them in to_thread.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any, Optional

import chromadb
from openai import AsyncOpenAI, OpenAI

logger = logging.getLogger(__name__)

# OpenAI embedding API accepts up to ~2048 inputs; stay conservative.
_EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "64"))


class RAGService:
    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL") or None

        # Sync client kept for rare non-async paths / health probes
        self.openai = OpenAI(api_key=api_key, base_url=base_url)
        self.async_openai = AsyncOpenAI(api_key=api_key, base_url=base_url)

        self.embedding_model = os.getenv(
            "EMBEDDING_MODEL", "text-embedding-3-small"
        )
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "800"))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "120"))

        self._client: Optional[chromadb.HttpClient] = None
        self._collection = None

    # ------------------------------------------------------------------
    # Chroma connection (lazy)
    # ------------------------------------------------------------------
    def _connect(self) -> bool:
        if self._collection is not None:
            return True
        try:
            host = os.getenv("CHROMA_HOST", "localhost")
            port = int(os.getenv("CHROMA_PORT", "8001"))
            if host == "chroma":
                port = 8000

            self._client = chromadb.HttpClient(host=host, port=port)
            self._collection = self._client.get_or_create_collection(
                name="docs",
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(
                "Chroma connected | docs=%s", self._collection.count()
            )
            return True
        except Exception as e:
            logger.warning("Chroma unavailable: %s", e)
            self._client = None
            self._collection = None
            return False

    @property
    def available(self) -> bool:
        return self._connect()

    def count(self) -> int:
        if not self._connect() or self._collection is None:
            return 0
        return self._collection.count()

    # ------------------------------------------------------------------
    # Chunking – iterative (no recursion), O(n) over characters
    # ------------------------------------------------------------------
    def _split(self, text: str) -> list[str]:
        """
        Recursive-*style* splitter implemented iteratively.

        Prefers larger semantic boundaries first:
            paragraph → line → sentence → word → character

        Overlap is applied between consecutive chunks so retrieval
        does not lose context at boundaries.
        """
        if not text or not text.strip():
            return []

        size = self.chunk_size
        overlap = min(self.chunk_overlap, size // 2)
        separators = ["\n\n", "\n", ". ", " ", ""]

        def split_once(t: str, sep: str) -> list[str]:
            if not sep:
                return [t[i : i + size] for i in range(0, len(t), size)]
            return t.split(sep)

        def merge_parts(parts: list[str], sep: str) -> list[str]:
            """Greedily pack parts into chunks ≤ size."""
            out: list[str] = []
            current = ""
            for part in parts:
                candidate = (current + sep + part) if current else part
                if len(candidate) <= size:
                    current = candidate
                else:
                    if current:
                        out.append(current)
                    if len(part) > size:
                        out.append(part)  # refined by a finer separator later
                        current = ""
                    else:
                        current = part
            if current:
                out.append(current)
            return out

        # Start with the whole text; progressively refine oversized pieces
        pieces = [text]
        for sep in separators:
            next_pieces: list[str] = []
            for piece in pieces:
                if len(piece) <= size:
                    next_pieces.append(piece)
                else:
                    parts = split_once(piece, sep)
                    next_pieces.extend(merge_parts(parts, sep))
            pieces = next_pieces

        # Final hard-cut for any remaining giants + strip empties
        raw: list[str] = []
        for p in pieces:
            p = p.strip()
            if not p:
                continue
            if len(p) <= size:
                raw.append(p)
            else:
                for i in range(0, len(p), size):
                    chunk = p[i : i + size].strip()
                    if chunk:
                        raw.append(chunk)

        if not raw:
            return []

        # Apply overlap
        if overlap <= 0 or len(raw) == 1:
            return raw

        overlapped: list[str] = [raw[0]]
        for i in range(1, len(raw)):
            prev = overlapped[-1]
            tail = prev[-overlap:] if len(prev) > overlap else prev
            nxt = raw[i]
            if not nxt.startswith(tail):
                nxt = (tail + " " + nxt).strip()
            # Guard against accidental bloat past 1.5× size
            if len(nxt) > size + overlap:
                nxt = nxt[-(size + overlap) :]
            overlapped.append(nxt)

        return overlapped

    async def split_async(self, text: str) -> list[str]:
        """
        Run CPU-bound splitting off the event loop.

        Raises
        ------
        ValueError
            If ``text`` is empty/whitespace-only or exceeds the hard size limit.
        RuntimeError
            If chunking fails unexpectedly inside the worker thread.
        """
        if text is None:
            raise ValueError("text must not be None")
        if not isinstance(text, str):
            raise TypeError(f"text must be str, got {type(text).__name__}")
        if not text.strip():
            raise ValueError("text is empty or whitespace-only")

        # Guard against pathological inputs that would exhaust memory
        max_chars = int(os.getenv("CHUNK_MAX_CHARS", str(5_000_000)))
        if len(text) > max_chars:
            raise ValueError(
                f"text length ({len(text):,}) exceeds CHUNK_MAX_CHARS ({max_chars:,})"
            )

        try:
            chunks = await asyncio.to_thread(self._split, text)
        except Exception as exc:
            logger.exception("Chunking failed for text of length %d", len(text))
            raise RuntimeError(f"Chunking failed: {exc}") from exc

        if not chunks:
            # _split already returns [] for blank input, but defend anyway
            raise ValueError("Chunking produced no output")

        return chunks

    # ------------------------------------------------------------------
    # Embeddings – async + batched
    # ------------------------------------------------------------------
    async def _embed_async(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        vectors: list[list[float]] = []
        for i in range(0, len(texts), _EMBED_BATCH_SIZE):
            batch = texts[i : i + _EMBED_BATCH_SIZE]
            resp = await self.async_openai.embeddings.create(
                model=self.embedding_model,
                input=batch,
            )
            vectors.extend(d.embedding for d in resp.data)
        return vectors

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """Sync fallback (tests / scripts). Prefer _embed_async in request path."""
        if not texts:
            return []
        vectors: list[list[float]] = []
        for i in range(0, len(texts), _EMBED_BATCH_SIZE):
            batch = texts[i : i + _EMBED_BATCH_SIZE]
            resp = self.openai.embeddings.create(
                model=self.embedding_model,
                input=batch,
            )
            vectors.extend(d.embedding for d in resp.data)
        return vectors

    # ------------------------------------------------------------------
    # Ingest
    # ------------------------------------------------------------------
    async def ingest(
        self,
        text: str,
        source: str = "upload",
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        if not self._connect() or self._collection is None:
            raise RuntimeError("Chroma is not available")

        # 1. Chunk off the event loop
        chunks = await self.split_async(text)
        if not chunks:
            raise ValueError("No content to ingest")

        # 2. Embed in batches (already async I/O)
        embeddings = await self._embed_async(chunks)

        ids = [str(uuid.uuid4()) for _ in chunks]
        metas = [
            {
                "source": source,
                "chunk_index": i,
                "total_chunks": len(chunks),
                **(metadata or {}),
            }
            for i in range(len(chunks))
        ]

        # 3. Chroma write is sync HTTP – keep it off the loop
        def _add() -> int:
            assert self._collection is not None
            self._collection.add(
                ids=ids,
                documents=chunks,
                embeddings=embeddings,
                metadatas=metas,
            )
            return self._collection.count()

        total = await asyncio.to_thread(_add)
        logger.info(
            "Ingested %d chunks from %s (kb=%d)", len(chunks), source, total
        )
        return {
            "source": source,
            "chunks": len(chunks),
            "total_docs": total,
        }

    # ------------------------------------------------------------------
    # Retrieve
    # ------------------------------------------------------------------
    async def retrieve(self, query: str, k: int = 4) -> list[dict[str, Any]]:
        if not self._connect() or self._collection is None:
            return []
        n = self._collection.count()
        if n == 0:
            return []

        q_emb = (await self._embed_async([query]))[0]

        def _query() -> dict:
            assert self._collection is not None
            return self._collection.query(
                query_embeddings=[q_emb],
                n_results=min(k, n),
                include=["documents", "metadatas", "distances"],
            )

        results = await asyncio.to_thread(_query)

        docs: list[dict[str, Any]] = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                dist = (
                    results["distances"][0][i] if results["distances"] else 1.0
                )
                docs.append(
                    {
                        "content": doc,
                        "metadata": (results["metadatas"] or [[]])[0][i]
                        if results["metadatas"]
                        else {},
                        "score": max(0.0, 1.0 - dist),
                    }
                )
        return docs

    def build_context(self, docs: list[dict[str, Any]]) -> str:
        if not docs:
            return ""
        parts = []
        for i, d in enumerate(docs, 1):
            src = d["metadata"].get("source", "unknown")
            parts.append(
                f"[{i}] (source: {src}, relevance: {d['score']:.2f})\n{d['content']}"
            )
        return "\n\n".join(parts)

    def reset(self) -> None:
        if not self._connect() or self._client is None:
            raise RuntimeError("Chroma is not available")
        try:
            self._client.delete_collection("docs")
        except Exception:
            pass
        self._collection = self._client.get_or_create_collection(
            name="docs",
            metadata={"hnsw:space": "cosine"},
        )
        logger.warning("Knowledge base reset")


_rag: Optional[RAGService] = None


def get_rag() -> RAGService:
    global _rag
    if _rag is None:
        _rag = RAGService()
    return _rag
