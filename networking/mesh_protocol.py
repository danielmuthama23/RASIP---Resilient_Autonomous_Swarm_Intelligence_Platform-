from __future__ import annotations
import asyncio, json, time
from dataclasses import dataclass, field
from threading   import Lock
from typing      import Dict, List, Set

HEARTBEAT_INTERVAL = 5.0   # seconds between pings
NODE_TIMEOUT       = 15.0  # seconds before marking dead
SEEN_CAP           = 10_000 # max dedup message IDs kept

@dataclass
class MeshNode:
    node_id:   str
    addr:      str         # host:port
    drone_id:  str
    last_seen: float = field(default_factory=time.time)
    alive:     bool  = True
    hops:      int   = 0

class MANETMesh:
    """
    Mobile Ad-hoc NETwork manager.
    Handles peer registration, heartbeat keepalive,
    flood broadcast with message-ID deduplication,
    and dead-node eviction triggering consensus re-vote.
    """

    def __init__(self, node_id: str, addr: str):
        self.node_id = node_id
        self.addr    = addr
        self._peers: Dict[str, MeshNode] = {}
        self._lock   = Lock()
        self._seen:  Set[str] = set()

    # ── Registration ──────────────────────────────────────
    def register(self, node: MeshNode) -> None:
        with self._lock:
            node.last_seen = time.time()
            node.alive     = True
            self._peers[node.node_id] = node

    def deregister(self, node_id: str) -> None:
        with self._lock:
            self._peers.pop(node_id, None)

    # ── Heartbeat loop ────────────────────────────────────
    async def heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            now, dead = time.time(), []
            with self._lock:
                for nid, node in self._peers.items():
                    if now - node.last_seen > NODE_TIMEOUT:
                        node.alive = False
                        dead.append(nid)
            for nid in dead:
                await self.broadcast({"type": "node_dead", "node_id": nid})

    # ── Flood broadcast with dedup ────────────────────────
    async def broadcast(self, msg: dict) -> None:
        """Flood to all alive peers; drop if msg_id already seen."""
        mid = msg.get("msg_id")
        if mid:
            if mid in self._seen: return
            self._seen.add(mid)
            if len(self._seen) > SEEN_CAP:
                self._seen = set(list(self._seen)[-SEEN_CAP//2:])

        with self._lock:
            alive = [n for n in self._peers.values() if n.alive]
        payload = json.dumps(msg).encode()
        await asyncio.gather(*[
            self._send_to(peer, payload) for peer in alive
        ], return_exceptions=True)

    async def _send_to(self, peer: MeshNode, payload: bytes) -> None:
        from .quic_transport import QUICTransport
        await QUICTransport.send(peer.addr, payload)

    # ── Topology query ────────────────────────────────────
    def topology(self) -> List[Dict]:
        with self._lock:
            return [
                {"node_id": n.node_id, "drone_id": n.drone_id,
                 "addr": n.addr, "alive": n.alive,
                 "hops": n.hops, "last_seen": n.last_seen}
                for n in self._peers.values()
            ]

    def alive_count(self) -> int:
        with self._lock:
            return sum(1 for n in self._peers.values() if n.alive)
