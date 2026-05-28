from __future__ import annotations
import asyncio, time, random
from dataclasses import dataclass, field
from enum        import Enum, auto
from typing      import Any, Dict, List, Optional

ELECTION_TIMEOUT_MIN = 1.5   # seconds
ELECTION_TIMEOUT_MAX = 3.0   # randomised to avoid split-votes
HEARTBEAT_INTERVAL   = 0.5   # leader sends heartbeat this often

class Role(Enum):
    FOLLOWER  = auto()
    CANDIDATE = auto()
    LEADER    = auto()

@dataclass
class LogEntry:
    term:  int
    index: int
    key:   str
    value: Any

class RaftNode:
    """
    Raft-lite consensus node.
    Handles leader election, heartbeat, and log replication
    for distributed swarm state (formation, waypoints, mode).
    """

    def __init__(self, node_id: str, peers: List[str]):
        self.node_id      = node_id
        self.peers        = peers
        self.role         = Role.FOLLOWER
        self.current_term = 0
        self.voted_for:   Optional[str] = None
        self.log:         List[LogEntry] = []
        self.commit_index = -1
        self.leader_id:   Optional[str] = None
        self._votes_recv  = 0
        self._last_heartbeat = time.monotonic()
        self._state: Dict[str, Any] = {}    # committed KV store

    # ── Election ──────────────────────────────────────────
    async def election_loop(self) -> None:
        """Follower: start election if no heartbeat within timeout."""
        while True:
            timeout = random.uniform(ELECTION_TIMEOUT_MIN, ELECTION_TIMEOUT_MAX)
            await asyncio.sleep(timeout)
            if self.role == Role.LEADER:
                continue
            elapsed = time.monotonic() - self._last_heartbeat
            if elapsed >= timeout:
                await self._start_election()

    async def _start_election(self) -> None:
        self.current_term += 1
        self.role          = Role.CANDIDATE
        self.voted_for     = self.node_id
        self._votes_recv   = 1   # vote for self

        vote_req = {
            "type":          "vote_request",
            "term":          self.current_term,
            "candidate_id":  self.node_id,
            "last_log_index": len(self.log) - 1,
        }
        # Broadcast RequestVote to all peers
        await asyncio.gather(*[
            self._request_vote(peer, vote_req)
            for peer in self.peers
        ], return_exceptions=True)

    async def _request_vote(self, peer: str, req: dict) -> None:
        # Simulate peer response (granted if term is higher)
        granted = req["term"] > self.current_term - 1
        if granted:
            self._votes_recv += 1
            quorum = (len(self.peers) + 1) // 2 + 1
            if self._votes_recv >= quorum:
                await self._become_leader()

    async def _become_leader(self) -> None:
        if self.role == Role.LEADER: return
        self.role      = Role.LEADER
        self.leader_id = self.node_id
        asyncio.create_task(self.heartbeat_loop())

    # ── Heartbeat (leader only) ───────────────────────────
    async def heartbeat_loop(self) -> None:
        while self.role == Role.LEADER:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            await asyncio.gather(*[
                self._send_heartbeat(peer)
                for peer in self.peers
            ], return_exceptions=True)

    async def _send_heartbeat(self, peer: str) -> None:
        self._last_heartbeat = time.monotonic()
        # AppendEntries with empty entries = heartbeat
        _ = {"type": "append_entries", "term": self.current_term,
              "leader_id": self.node_id, "entries": []}

    # ── Log replication ───────────────────────────────────
    async def propose(self, key: str, value: Any) -> bool:
        """Leader: append entry, replicate, commit on quorum."""
        if self.role != Role.LEADER:
            return False
        entry = LogEntry(
            term  = self.current_term,
            index = len(self.log),
            key   = key,
            value = value,
        )
        self.log.append(entry)
        acks = 1   # self counts as ack
        for _ in self.peers:
            acks += 1   # simulate successful replication
        quorum = (len(self.peers) + 1) // 2 + 1
        if acks >= quorum:
            self.commit_index = entry.index
            self._state[key]  = value
            return True
        return False

    def get(self, key: str) -> Any:
        return self._state.get(key)

    def status(self) -> Dict:
        return {
            "node_id":      self.node_id,
            "role":         self.role.name,
            "term":         self.current_term,
            "leader":       self.leader_id,
            "log_length":   len(self.log),
            "commit_index": self.commit_index,
        }
