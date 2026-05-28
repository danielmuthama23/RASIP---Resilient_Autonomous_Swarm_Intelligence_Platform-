from __future__ import annotations
import asyncio
from typing import List, Dict, Any

from .vector_store import VectorStore

MIN_SCORE   = 0.55   # discard chunks below this cosine similarity
MAX_CONTEXT = 4096  # max characters returned in one context blob

class RAGRetriever:
    """
    Async retriever: query → embed → ANN search → re-rank
    → assemble context string for LLM / Copilot Studio.
    """

    def __init__(self, store: VectorStore | None = None):
        self._store = store or VectorStore()

    # ── Main query entry point ────────────────────────────
    async def query(
        self,
        question:   str,
        top_k:      int  = 8,
        filter_tag: str | None = None,
    ) -> Dict[str, Any]:
        """
        Returns {context, sources, n_retrieved}.
        context  — assembled text passed to the LLM
        sources  — list of {text, score, tag} metadata dicts
        """
        # Run blocking Qdrant search in a thread pool
        loop = asyncio.get_event_loop()
        hits = await loop.run_in_executor(
            None,
            lambda: self._store.search(question, top_k, filter_tag),
        )

        # Re-rank: drop low-confidence chunks
        ranked = self._rerank(hits)

        # Assemble context string, respect MAX_CONTEXT budget
        context = self._assemble(ranked)

        return {
            "context":      context,
            "sources":      ranked,
            "n_retrieved":  len(ranked),
        }

    # ── Re-ranking ────────────────────────────────────────
    def _rerank(self, hits: List[Dict]) -> List[Dict]:
        """Filter by MIN_SCORE; sort descending by score."""
        filtered = [h for h in hits if h["score"] >= MIN_SCORE]
        return sorted(filtered, key=lambda h: h["score"], reverse=True)

    # ── Context assembly ──────────────────────────────────
    def _assemble(self, ranked: List[Dict]) -> str:
        """Concatenate chunk texts up to MAX_CONTEXT characters."""
        parts, total = [], 0
        for h in ranked:
            text = h["text"].strip()
            if total + len(text) > MAX_CONTEXT:
                # Partial include to fill budget exactly
                remaining = MAX_CONTEXT - total
                parts.append(text[:remaining])
                break
            parts.append(text)
            total += len(text)
        return "

".join(parts)

    # ── Convenience: batch-index new docs on the fly ──────
    async def index(self, texts: List[str], tag: str = "general") -> int:
        """Embed and upsert a list of raw text strings."""
        from .vector_store import Chunk
        chunks = [Chunk(text=t, metadata={"tag": tag}) for t in texts]
        loop   = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self._store.upsert(chunks))
        return len(chunks)

    # ── Introspection ─────────────────────────────────────
    async def store_size(self) -> int:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._store.count)
