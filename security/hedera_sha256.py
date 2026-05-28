from __future__ import annotations
import hashlib, json, time
from threading  import Lock
from typing     import Any, Dict, List, Optional
from dataclasses import dataclass

# ── TX record ─────────────────────────────────────────
@dataclass
class HederaTx:
    tx_id:     str
    entity_id: str     # drone_id, operator_id, or any entity
    hash:      str     # SHA-256 hex of signed payload
    prev_hash: str     # links to prior TX (chain integrity)
    timestamp: float
    valid:     bool = True
    meta:      Dict[str, Any] = None

    def __post_init__(self):
        if self.meta is None: self.meta = {}

class HederaSHA256:
    """
    Cross-module Hedera-inspired SHA-256 identity ledger.
    This top-level security/ version adds chain linking —
    each TX records the prev_hash, forming a tamper-evident
    chain. Divergence from the expected chain is detected
    during verify() and triggers entity quarantine.
    """

    _ledger:    List[HederaTx]        = []
    _index:     Dict[str, str]        = {}   # entity → latest hash
    _chain_tip: Dict[str, str]        = {}   # entity → prev_hash
    _quarantine: set                  = set()
    _lock:      Lock                  = Lock()

    # ── Sign ──────────────────────────────────────────────
    @classmethod
    def sign(cls, entity_id: str, payload: Any,
             meta: Dict | None = None) -> str:
        """
        Hash payload, link to previous TX, append to ledger.
        Returns SHA-256 hex digest.
        """
        raw    = json.dumps(payload, sort_keys=True).encode()
        digest = hashlib.sha256(raw).hexdigest()
        tx_id  = f"TX-{entity_id}-{int(time.time() * 1000)}"

        with cls._lock:
            prev = cls._chain_tip.get(entity_id, "GENESIS")
            tx   = HederaTx(
                tx_id     = tx_id,
                entity_id = entity_id,
                hash      = digest,
                prev_hash = prev,
                timestamp = time.time(),
                meta      = meta or {},
            )
            cls._ledger.append(tx)
            cls._index[entity_id]     = digest
            cls._chain_tip[entity_id] = digest
            # Cap at 200 000 TXs — prune oldest 50 000
            if len(cls._ledger) > 200_000:
                cls._ledger = cls._ledger[-150_000:]
        return digest

    # ── Verify ────────────────────────────────────────────
    @classmethod
    def verify(cls, entity_id: str, payload: Any) -> Dict:
        """
        Re-hash payload; compare with latest known hash.
        On mismatch: quarantine entity, mark TX invalid.
        Returns {match, expected, received, quarantined}.
        """
        raw      = json.dumps(payload, sort_keys=True).encode()
        received = hashlib.sha256(raw).hexdigest()
        with cls._lock:
            expected = cls._index.get(entity_id, "")
        match = (received == expected)
        if not match:
            cls._quarantine_entity(entity_id)
        return {
            "match":       match,
            "expected":    expected,
            "received":    received,
            "quarantined": entity_id in cls._quarantine,
        }

    # ── Chain integrity check ─────────────────────────────
    @classmethod
    def verify_chain(cls, entity_id: str) -> bool:
        """Walk the entity's TX chain; return False if broken."""
        with cls._lock:
            txs = [t for t in cls._ledger
                   if t.entity_id == entity_id]
        if not txs: return True
        for i in range(1, len(txs)):
            if txs[i].prev_hash != txs[i - 1].hash:
                return False
        return True

    # ── Quarantine ────────────────────────────────────────
    @classmethod
    def _quarantine_entity(cls, entity_id: str) -> None:
        cls._quarantine.add(entity_id)
        with cls._lock:
            for tx in reversed(cls._ledger):
                if tx.entity_id == entity_id:
                    tx.valid = False
                    break

    @classmethod
    def is_quarantined(cls, entity_id: str) -> bool:
        return entity_id in cls._quarantine

    @classmethod
    def clear_quarantine(cls, entity_id: str) -> None:
        cls._quarantine.discard(entity_id)

    # ── REST helper ───────────────────────────────────────
    @classmethod
    def ledger(cls, entity_id: Optional[str] = None,
              limit: int = 100) -> List[Dict]:
        with cls._lock:
            txs = cls._ledger[-limit:] if not entity_id else [
                t for t in cls._ledger if t.entity_id == entity_id
            ][-limit:]
        return [
            {"txId": t.tx_id, "entityId": t.entity_id,
             "hash": t.hash, "prevHash": t.prev_hash,
             "ts": t.timestamp, "valid": t.valid,
             "meta": t.meta}
            for t in reversed(txs)
        ]
