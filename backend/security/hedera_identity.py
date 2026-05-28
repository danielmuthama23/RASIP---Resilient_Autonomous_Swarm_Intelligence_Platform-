from __future__ import annotations
import hashlib, json, time
from threading  import Lock
from typing     import Any, Dict, List
from dataclasses import dataclass, field

# ── TX record ─────────────────────────────────────────
@dataclass
class HederaTx:
    tx_id:     str
    drone_id:  str
    hash:      str        # SHA-256 hex digest of payload
    timestamp: float
    valid:     bool = True

class HederaIdentity:
    """
    Hedera-inspired SHA-256 identity ledger.
    Each drone signs its telemetry; the ledger is append-only.
    Unverified frames are quarantined, not broadcast.
    """

    _ledger: List[HederaTx] = []
    _index:  Dict[str, str] = {}   # drone_id → latest hash
    _lock:   Lock           = Lock()

    # ── Sign a payload ────────────────────────────────────
    @classmethod
    def sign(cls, drone_id: str, payload: Any) -> str:
        """SHA-256 hash payload, append TX to ledger, return hex digest."""
        raw    = json.dumps(payload, sort_keys=True).encode()
        digest = hashlib.sha256(raw).hexdigest()
        tx_id  = f"TX-{drone_id}-{int(time.time()*1000)}"

        tx = HederaTx(
            tx_id     = tx_id,
            drone_id  = drone_id,
            hash      = digest,
            timestamp = time.time(),
        )
        with cls._lock:
            cls._ledger.append(tx)
            cls._index[drone_id] = digest
            # Prune ledger: keep latest 10 000 TXs per drone
            if len(cls._ledger) > 100_000:
                cls._ledger = cls._ledger[-100_000:]
        return digest

    # ── Verify a payload ──────────────────────────────────
    @classmethod
    def verify(cls, drone_id: str, payload: Any) -> Dict:
        """
        Re-hash payload; compare with last known hash for drone.
        Returns {match, expected, received}.
        """
        raw      = json.dumps(payload, sort_keys=True).encode()
        received = hashlib.sha256(raw).hexdigest()
        with cls._lock:
            expected = cls._index.get(drone_id, "")
        match = (received == expected)
        if not match:
            cls._quarantine(drone_id)
        return {"match": match, "expected": expected, "received": received}

    # ── Quarantine a rogue frame ──────────────────────────
    @classmethod
    def _quarantine(cls, drone_id: str):
        with cls._lock:
            for tx in reversed(cls._ledger):
                if tx.drone_id == drone_id:
                    tx.valid = False
                    break

    # ── REST helper ───────────────────────────────────────
    @classmethod
    def ledger(cls, limit: int = 100) -> List[Dict]:
        """Return the most recent TXs as dicts (for GET /hashes)."""
        with cls._lock:
            recent = cls._ledger[-limit:]
        return [
            {
                "txId":      tx.tx_id,
                "droneId":   tx.drone_id,
                "hash":      tx.hash,
                "timestamp": tx.timestamp,
                "valid":     tx.valid,
            }
            for tx in reversed(recent)
        ]
