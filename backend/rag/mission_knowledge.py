from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing   import List, Dict, Any

from .vector_store import VectorStore, Chunk
from .retriever    import RAGRetriever

# ── Static doctrine chunks seeded at startup ─────────
DOCTRINE: List[str] = [
    "V-WING formation: leader at apex, two trailing wings. "
    "Optimal for linear advance through open terrain.",

    "CIRCLE formation: perimeter defence. All drones face "
    "outward. Use when protecting a static asset.",

    "SEARCH formation: parallel sweep lanes 50 m apart. "
    "Maximises area coverage for reconnaissance missions.",

    "Obstacle reroute protocol: if distance < 5 m, increase "
    "altitude by 20 m and activate SEARCH mode temporarily.",

    "GPS degradation fallback chain: GPS → Visual SLAM → "
    "swarm-relative positioning from nearest healthy peer.",

    "Battery low threshold: 20%. Drone auto-returns to base "
    "and consensus vote redistributes its formation slot.",

    "Consensus quorum: 92% drone agreement required before "
    "any formation or waypoint change is committed.",

    "Hedera identity: each telemetry frame is SHA-256 signed. "
    "Unverified frames are quarantined, not broadcast.",

    "YOLO detection confidence < 0.6 triggers a re-scan pass "
    "at lower altitude before logging a confirmed detect.",

    "Fabric streaming: anomaly z-score > 2σ from fleet mean "
    "raises an alert and queues a model retraining job.",
]

class MissionKnowledge:
    """
    Manages the swarm's long-term RAG memory:
      • Seeds static tactical doctrine at startup
      • Indexes live mission events as they occur
      • Provides a query interface for Copilot Studio / ATC
    """

    def __init__(self):
        self._store     = VectorStore()
        self._retriever = RAGRetriever(self._store)
        self._seeded    = False

    # ── Startup seed ──────────────────────────────────────
    async def seed(self) -> None:
        """Upsert doctrine chunks once; skip if already seeded."""
        if self._seeded: return
        if await self._retriever.store_size() > 0:
            self._seeded = True
            return
        chunks = [
            Chunk(text=d, metadata={"tag": "doctrine", "static": True})
            for d in DOCTRINE
        ]
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self._store.upsert(chunks))
        self._seeded = True

    # ── Live event indexing ───────────────────────────────
    async def record_event(self, event: Dict[str, Any]) -> None:
        """
        Index a live mission event (obstacle, alert, formation
        change, YOLO detect) so future RAG queries surface it.
        """
        ts   = datetime.now(timezone.utc).isoformat()
        text = (
            f"[{ts}] {event.get('type', 'EVENT').upper()}: "
            f"{event.get('description', '')}"
        )
        chunk = Chunk(
            text     = text,
            metadata = {
                "tag":       "live_event",
                "event_type": event.get("type"),
                "drone_id":  event.get("drone_id"),
                "ts":        ts,
                "static":    False,
            },
        )
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self._store.upsert([chunk]))

    # ── Query interface ───────────────────────────────────
    async def query(self, question: str, tag: str | None = None) -> Dict:
        """Retrieve relevant context for a natural-language question."""
        return await self._retriever.query(question, filter_tag=tag)

    async def query_doctrine(self, question: str) -> Dict:
        """Query only static doctrine chunks."""
        return await self.query(question, tag="doctrine")

    async def query_events(self, question: str) -> Dict:
        """Query only live mission events."""
        return await self.query(question, tag="live_event")

    # ── Housekeeping ──────────────────────────────────────
    async def prune_events(self, keep_latest: int = 500) -> None:
        """
        Drop oldest live_event chunks beyond keep_latest.
        Doctrine chunks are never pruned.
        """
        # Scroll all live_event ids sorted by ts ascending
        hits = self._store.search(
            query      = "mission event",
            top_k      = 9999,
            filter_tag = "live_event",
        )
        if len(hits) <= keep_latest: return
        to_drop = hits[keep_latest:]  # oldest are ranked lower
        loop = asyncio.get_event_loop()
        for h in to_drop:
            await loop.run_in_executor(
                None, lambda hid=h["id"]: self._store.delete(hid)
            )
