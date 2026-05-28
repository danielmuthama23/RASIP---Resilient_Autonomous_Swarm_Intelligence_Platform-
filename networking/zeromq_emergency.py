from __future__ import annotations
import asyncio, json, os
from dataclasses import dataclass, field
from typing      import Any, Callable, Dict, List
import time

# pyzmq — installed separately, not a core dep
ZMQ_PUSH_ADDR = os.getenv("ZMQ_PUSH_ADDR", "tcp://*:5555")
ZMQ_PULL_ADDR = os.getenv("ZMQ_PULL_ADDR", "tcp://localhost:5555")
PRIORITY_TYPES = {"MAYDAY", "REROUTE", "LAND_NOW", "ABORT"}

@dataclass
class EmergencyMessage:
    msg_type:   str
    drone_id:   str
    payload:    Any
    priority:   int   = 10    # higher = more urgent
    timestamp:  float = field(default_factory=time.time)

    def to_bytes(self) -> bytes:
        return json.dumps({
            "type":      self.msg_type,
            "drone_id":  self.drone_id,
            "payload":   self.payload,
            "priority":  self.priority,
            "ts":        self.timestamp,
        }).encode()

    @classmethod
    def from_bytes(cls, raw: bytes) -> EmergencyMessage:
        d = json.loads(raw)
        return cls(
            msg_type  = d["type"],
            drone_id  = d["drone_id"],
            payload   = d["payload"],
            priority  = d.get("priority", 10),
            timestamp = d.get("ts", time.time()),
        )

class ZeroMQEmergency:
    """
    Last-resort ZeroMQ PUSH/PULL emergency channel.
    Activated only when both QUIC and MQTT are unavailable.
    Uses PUSH socket for sending, PULL socket for receiving.
    Priority queue ensures MAYDAY/ABORT messages sent first.
    """

    def __init__(self):
        self._push_sock = None
        self._pull_sock = None
        self._handlers: Dict[str, Callable] = {}
        self._queue:    List[EmergencyMessage] = []
        self._active    = False

    # ── Initialise ZMQ sockets ────────────────────────────
    async def start(self) -> None:
        """Bind PUSH and connect PULL sockets."""
        try:
            import zmq.asyncio as zmq
            ctx = zmq.Context()
            self._push_sock = ctx.socket(zmq.PUSH)
            self._push_sock.bind(ZMQ_PUSH_ADDR)
            self._pull_sock = ctx.socket(zmq.PULL)
            self._pull_sock.connect(ZMQ_PULL_ADDR)
            self._active = True
            asyncio.create_task(self._recv_loop())
        except ImportError:
            self._active = False   # pyzmq not installed

    # ── Send emergency message ────────────────────────────
    async def send(self, msg: EmergencyMessage) -> bool:
        """
        Enqueue and transmit. PRIORITY_TYPES jump the queue.
        Returns False if ZMQ not available.
        """
        if not self._active: return False

        # High-priority messages go to the front
        if msg.msg_type in PRIORITY_TYPES:
            self._queue.insert(0, msg)
        else:
            self._queue.append(msg)

        await self._flush_queue()
        return True

    async def _flush_queue(self) -> None:
        while self._queue and self._push_sock:
            msg = self._queue.pop(0)
            await self._push_sock.send(msg.to_bytes())

    # ── Receive loop ──────────────────────────────────────
    async def _recv_loop(self) -> None:
        """Continuously poll PULL socket and dispatch messages."""
        while self._active and self._pull_sock:
            try:
                raw = await asyncio.wait_for(
                    self._pull_sock.recv(), timeout=1.0)
                msg = EmergencyMessage.from_bytes(raw)
                handler = self._handlers.get(msg.msg_type)
                if handler: await handler(msg)
            except asyncio.TimeoutError:
                continue
            except Exception:
                break

    # ── Handler registration ──────────────────────────────
    def on(self, msg_type: str) -> Callable:
        """Decorator: register handler for an emergency message type."""
        def decorator(fn: Callable):
            self._handlers[msg_type] = fn
            return fn
        return decorator

    # ── Convenience helpers ───────────────────────────────
    async def mayday(self, drone_id: str, reason: str) -> bool:
        """Fire a MAYDAY with highest priority."""
        return await self.send(EmergencyMessage(
            msg_type="MAYDAY", drone_id=drone_id,
            payload={"reason": reason}, priority=100,
        ))

    async def abort(self, drone_id: str) -> bool:
        """Immediate mission abort signal."""
        return await self.send(EmergencyMessage(
            msg_type="ABORT", drone_id=drone_id,
            payload={}, priority=99,
        ))

    def status(self) -> Dict:
        return {"active": self._active,
                "queue_len": len(self._queue),
                "push_addr": ZMQ_PUSH_ADDR,
                "handlers": list(self._handlers.keys())}
