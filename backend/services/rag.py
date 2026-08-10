"""
RAG service – Chroma (HTTP) + OpenAI embeddings + recursive chunking.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Optional

import chromadb
from openai import OpenAI

logger = logging.getLogger(__name__)


class RAGService:
    def __init__(self) -> None:
        self.openai = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL") or None,
        )
        self.embedding_model = os.getenv(
            "EMBEDDING_MODEL", "text-embedding-3-small"
        )
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "800"))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "120"))

        self._client: Optional[chromadb.HttpClient] = None
        self._collection = None

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

    def _split(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []

        separators = ["\n\n", "\n", ". ", " ", ""]
        chunks: list[str] = []

        def _recurse(t: str, seps: list[str]) -> None:
            if len(t) <= self.chunk_size:
                if t.strip():
                    chunks.append(t.strip())
                return
            sep = seps[0] if seps else ""
            parts = t.split(sep) if sep else list(t)
            current = ""
            for part in parts:
                candidate = (current + sep + part) if current else part
                if len(candidate) <= self.chunk_size:
                    current = candidate
                else:
                    if current:
                        chunks.append(current.strip())
                    if len(part) > self.chunk_size and len(seps) > 1:
                        _recurse(part, seps[1:])
                        current = ""
                    else:
                        current = part
            if current.strip():
                if chunks and self.chunk_overlap > 0:
                    prev = chunks[-1]
                    overlap = prev[-self.chunk_overlap :] if len(prev) > self.chunk_overlap else prev
                    if not current.startswith(overlap):
                        current = overlap + " " + current
                chunks.append(current.strip())

        _recurse(text, separators)
        return [c for c in chunks if c]

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = self.openai.embeddings.create(
            model=self.embedding_model,
            input=texts,
        )
        return [d.embedding for d in resp.data]

    def ingest(
        self,
        text: str,
        source: str = "upload",
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        if not self._connect() or self._collection is None:
            raise RuntimeError("Chroma is not available")

        chunks = self._split(text)
        if not chunks:
            raise ValueError("No content to ingest")

        embeddings = self._embed(chunks)
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

        self._collection.add(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metas,
        )
        return {
            "source": source,
            "chunks": len(chunks),
            "total_docs": self._collection.count(),
        }

    def retrieve(self, query: str, k: int = 4) -> list[dict[str, Any]]:
        if not self._connect() or self._collection is None:
            return []
        n = self._collection.count()
        if n == 0:
            return []

        q_emb = self._embed([query])[0]
        results = self._collection.query(
            query_embeddings=[q_emb],
            n_results=min(k, n),
            include=["documents", "metadatas", "distances"],
        )

        docs: list[dict[str, Any]] = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                dist = results["distances"][0][i] if results["distances"] else 1.0
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
