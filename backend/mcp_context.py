import asyncio
from collections import deque
from threading   import Lock
from typing      import Any, Deque, Dict, List

HISTORY_LEN  = 50     # snapshots kept per drone
CONSENSUS_TH = 0.92  # quorum fraction for commit

class MCPContextEngine:
    """
    Thread-safe shared drone context store.
    Used by: TelemetryGenerator, BoidsEngine, SwarmConsensus,
             REST endpoints, Copilot Studio / MCP tools.
    """

    def __init__(self):
        self._lock:    Lock                      = Lock()
        self._drones:  Dict[str, Deque]          = {}
        self._mission: Dict[str, Any]            = {
            "formation": "V-WING",
            "mode":      "SEARCH",
        }
        self._votes:   Dict[str, Dict[str, str]] = {}

    # ── Telemetry update (called every tick) ──────────────
    def update(self, drones: List[Dict]) -> None:
        with self._lock:
            for d in drones:
                did = d["id"]
                if did not in self._drones:
                    self._drones[did] = deque(maxlen=HISTORY_LEN)
                self._drones[did].append(d)

    # ── Consensus vote ────────────────────────────────────
    def vote(self, drone_id: str, key: str, value: str) -> float:
        """Cast vote; return current agreement fraction."""
        with self._lock:
            self._votes.setdefault(key, {})[drone_id] = value
            votes = self._votes[key]
            top   = max(set(votes.values()),
                       key=lambda v: list(votes.values()).count(v))
            agree = sum(1 for v in votes.values() if v == top)
            return agree / len(votes)

    # ── Snapshot for REST / Copilot Studio ───────────────
    def snapshot(self) -> Dict:
        with self._lock:
            latest = {
                did: list(hist)[-1]
                for did, hist in self._drones.items()
                if hist
            }
            return {
                "drones":    latest,
                "mission":   dict(self._mission),
                "consensus": self._consensus_score(),
                "n_nodes":   len(self._drones),
            }

    def _consensus_score(self) -> float:
        if not self._votes: return 1.0
        scores = []
        for votes in self._votes.values():
            top   = max(set(votes.values()),
                       key=lambda v: list(votes.values()).count(v))
            agree = sum(1 for v in votes.values() if v == top)
            scores.append(agree / len(votes))
        return sum(scores) / len(scores)

    # ── Mission state helpers ─────────────────────────────
    def set_mission(self, key: str, value: Any) -> None:
        with self._lock:
            self._mission[key] = value

    def get_mission(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._mission.get(key, default)
