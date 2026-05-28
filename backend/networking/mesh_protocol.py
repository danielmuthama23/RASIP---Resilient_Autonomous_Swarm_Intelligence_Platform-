from __future__ import annotations
import asyncio, time, json
from dataclasses import dataclass, field
from threading   import Lock
from typing      import Dict, List, Set

HEARTBEAT_INTERVAL = 5.0   # seconds between node pings
NODE_TIMEOUT       = 15.0  # mark node dead after this many seconds

# ── Node record ───────────────────────────────────────
@dataclass
class MeshNode:
    node_id:    str
    addr:       str          # host:port
    drone_id:   str
    last_seen:  float = field(default_factory=time.time)
    alive:      bool  = True
    hops:       int   = 0    # distance from this node in mesh

class MANETMesh:
    """
    Mobile Ad-hoc NETwork manager.
    Handles peer registration, heartbeat, and best-path
    broadcast routing across the drone mesh.
    """

    def __init__(self, node_id: str, addr: str):
        self.node_id  = node_id
        self.addr     = addr
        self._peers:  Dict[str, MeshNode] = {}
        self._lock    = Lock()
        self._seen:   Set[str] = set()   # dedup broadcast msg IDs

    # ── Registration ──────────────────────────────────────
    def register(self, node: MeshNode) -> None:
        """Add or refresh a peer node."""
        with self._lock:
            node.last_seen = time.time()
            node.alive     = True
            self._peers[node.node_id] = node

    def deregister(self, node_id: str) -> None:
        with self._lock:
            self._peers.pop(node_id, None)

    # ── Heartbeat loop ────────────────────────────────────
    async def heartbeat_loop(self) -> None:
        """Periodically ping peers; mark stale nodes as dead."""
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            now  = time.time()
            dead = []
            with self._lock:
                for nid, node in self._peers.items():
                    if now - node.last_seen > NODE_TIMEOUT:
                        node.alive = False
                        dead.append(nid)
            if dead:
                await self._handle_dead_nodes(dead)

    async def _handle_dead_nodes(self, dead: List[str]) -> None:
        # Trigger consensus re-vote to redistribute dead slots
        for nid in dead:
            await self.broadcast({
                "type": "node_dead",
                "node_id": nid,
            })

    # ── Flood broadcast with dedup ────────────────────────
    async def broadcast(self, msg: dict) -> None:
        """
        Flood message to all alive peers.
        msg_id deduplication prevents loops in mesh cycles.
        """
        msg_id = msg.get("msg_id")
        if msg_id and msg_id in self._seen:
            return   # already forwarded — drop
        if msg_id:
            self._seen.add(msg_id)
            if len(self._seen) > 10_000:
                self._seen = set(list(self._seen)[-5_000:])

        with self._lock:
            alive = [n for n in self._peers.values() if n.alive]

        payload = json.dumps(msg).encode()
        await asyncio.gather(*[
            self._send_to(peer, payload)
            for peer in alive
        ], return_exceptions=True)

    async def _send_to(self, peer: MeshNode, payload: bytes) -> None:
        # Delegated to QUICTransport (injected at runtime)
        from .quic_transport import QUICTransport
        await QUICTransport.send(peer.addr, payload)

    # ── Topology query ────────────────────────────────────
    def topology(self) -> List[Dict]:
        """Return current mesh topology snapshot."""
        with self._lock:
            return [
                {
                    "node_id":  n.node_id,
                    "drone_id": n.drone_id,
                    "addr":     n.addr,
                    "alive":    n.alive,
                    "hops":     n.hops,
                    "last_seen": n.last_seen,
                }
                for n in self._peers.values()
            ]

    def alive_count(self) -> int:
        with self._lock:
            return sum(1 for n in self._peers.values() if n.alive)
