from __future__ import annotations
import uuid
import numpy as np
from typing           import List, Dict, Any
from dataclasses       import dataclass
from sentence_transformers import SentenceTransformer
from qdrant_client      import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams,
    PointStruct, Filter, FieldCondition, MatchValue
)

COLLECTION  = "rasip_knowledge"
EMBED_MODEL = "all-MiniLM-L6-v2"  # 384-dim, fast on CPU
DIM         = 384

@dataclass
class Chunk:
    text:     str
    metadata: Dict[str, Any]
    id:       str = ""

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())

class VectorStore:
    """
    Wraps Qdrant + sentence-transformers.
    Provides upsert, search, and filtered search.
    """

    def __init__(self, url: str = "http://localhost:6333"):
        self._encoder = SentenceTransformer(EMBED_MODEL)
        self._client  = QdrantClient(url=url)
        self._ensure_collection()

    def _ensure_collection(self):
        existing = [c.name for c in
                    self._client.get_collections().collections]
        if COLLECTION not in existing:
            self._client.create_collection(
                collection_name = COLLECTION,
                vectors_config  = VectorParams(
                    size     = DIM,
                    distance = Distance.COSINE,
                ),
            )

    # ── Write ─────────────────────────────────────────────
    def upsert(self, chunks: List[Chunk]) -> None:
        """Embed and upsert a batch of text chunks."""
        texts   = [c.text for c in chunks]
        vectors = self._encoder.encode(texts, show_progress_bar=False)

        points = [
            PointStruct(
                id      = c.id,
                vector  = vec.tolist(),
                payload = {"text": c.text, **c.metadata},
            )
            for c, vec in zip(chunks, vectors)
        ]
        self._client.upsert(
            collection_name = COLLECTION,
            points          = points,
        )

    # ── Read ──────────────────────────────────────────────
    def search(self, query: str, top_k: int = 5,
               filter_tag: str | None = None) -> List[Dict]:
        """Embed query; return top-k most similar chunks."""
        vec = self._encoder.encode([query])[0].tolist()

        filt = None
        if filter_tag:
            filt = Filter(must=[FieldCondition(
                key   = "tag",
                match = MatchValue(value=filter_tag),
            )])

        hits = self._client.search(
            collection_name = COLLECTION,
            query_vector    = vec,
            limit           = top_k,
            query_filter    = filt,
            with_payload    = True,
        )
        return [
            {"text": h.payload["text"], "score": h.score,
             **{k: v for k, v in h.payload.items() if k != "text"}}
            for h in hits
        ]

    def delete(self, chunk_id: str) -> None:
        self._client.delete(
            collection_name = COLLECTION,
            points_selector = [chunk_id],
        )

    def count(self) -> int:
        return self._client.get_collection(COLLECTION).points_count
