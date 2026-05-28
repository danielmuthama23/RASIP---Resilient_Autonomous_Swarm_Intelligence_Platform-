import asyncio
from collections import Counter
from typing      import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..mcp_context import MCPContextEngine

QUORUM       = 0.92  # 92% agreement required to commit
VOTE_TIMEOUT = 2.0   # seconds before a vote round expires

class SwarmConsensus:
    """
    Two-phase voting: leader proposes → drones vote → commit if
    quorum reached within VOTE_TIMEOUT. Mirrors Raft-lite semantics.
    """

    def __init__(self, mcp: 'MCPContextEngine'):
        self.mcp   = mcp
        self._log: List[Dict] = []   # committed entry log
        self._pending: Dict[str, Dict] = {}

    # ── Phase 1: leader proposes ─────────────────────────
    async def propose(self, key: str, value: Any) -> bool:
        """Broadcast proposal; gather drone votes; commit if quorum."""
        n_drones = self.mcp._drones.__len__()
        if n_drones == 0: return False

        proposal = {"key": key, "value": value, "votes": {}}
        self._pending[key] = proposal

        # Simulate each drone casting a vote (accept/reject)
        await asyncio.gather(*[
            self._drone_vote(did, key, value, proposal)
            for did in self.mcp._drones
        ])

        return await self._try_commit(key, n_drones)

    # ── Phase 2: each node votes ──────────────────────────
    async def _drone_vote(self, drone_id: str, key: str,
                          value: Any, proposal: dict):
        # Simulated network jitter (0–50 ms)
        await asyncio.sleep(asyncio.get_event_loop()
            .time() % 0.05)

        # Accept if drone is healthy (battery > 20%, signal > 30%)
        drone = list(self.mcp._drones[drone_id])[-1]
        accept = (
            drone.get("battery", 100) > 20 and
            drone.get("signal",  100) > 30
        )
        proposal["votes"][drone_id] = "accept" if accept else "reject"

    # ── Commit if quorum reached ──────────────────────────
    async def _try_commit(self, key: str, n_drones: int) -> bool:
        proposal = self._pending.get(key)
        if not proposal: return False

        counts   = Counter(proposal["votes"].values())
        accepted = counts.get("accept", 0)
        ratio    = accepted / n_drones

        if ratio >= QUORUM:
            # Commit to MCP state
            self.mcp._mission[key] = proposal["value"]
            self._log.append({
                "key":      key,
                "value":    proposal["value"],
                "accepted": accepted,
                "ratio":    ratio,
            })
            del self._pending[key]
            return True

        return False  # quorum not reached — proposal lapses

    # ── Query helpers ────────────────────────────────────
    def log(self) -> List[Dict]:
        """Return committed entry log (most recent first)."""
        return list(reversed(self._log))

    def consensus_score(self) -> float:
        """Fraction of last committed vote that accepted."""
        if not self._log: return 1.0
        return self._log[-1]["ratio"]
