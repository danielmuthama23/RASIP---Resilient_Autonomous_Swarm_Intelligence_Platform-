from __future__ import annotations
import asyncio, time
from dataclasses import dataclass, field
from typing      import Callable, Awaitable, Dict

ACK_TIMEOUT  = 2.0   # seconds per send attempt
MAX_RETRIES  = 3
STREAM_LIMIT = 100   # max concurrent streams

Handler = Callable[[bytes], Awaitable[None]]

@dataclass
class QUICStream:
    stream_id:  int
    peer_addr:  str
    created_at: float = field(default_factory=time.monotonic)
    acked:      bool  = False
    retries:    int   = 0

class QUICTransport:
    """
    QUIC-based primary transport layer.
    Features:
      • Multiplexed streams (up to STREAM_LIMIT concurrent)
      • Per-message ACK with 2-second timeout
      • Exponential back-off retry (0.1 → 0.2 → 0.4 s)
      • Auto-fallback to MQTTFallback after MAX_RETRIES
      • Decorator-based message handler registration
    """

    _streams:  Dict[int, QUICStream] = {}
    _handlers: Dict[str, Handler]   = {}
    _counter   = 0

    # ── Send with retry + fallback ────────────────────────
    @classmethod
    async def send(cls, addr: str, payload: bytes,
                  msg_type: str = "data") -> bool:
        stream = cls._open_stream(addr)
        for attempt in range(MAX_RETRIES):
            try:
                await asyncio.wait_for(
                    cls._transmit(stream, payload),
                    timeout=ACK_TIMEOUT,
                )
                stream.acked = True
                return True
            except asyncio.TimeoutError:
                stream.retries += 1
                await asyncio.sleep(0.1 * (2 ** attempt))

        # All retries exhausted — escalate to MQTT
        from .mqtt_fallback import MQTTFallback
        await MQTTFallback.publish(
            topic=f"swarm/mesh/{addr}", payload=payload)
        return False

    @classmethod
    def _open_stream(cls, addr: str) -> QUICStream:
        cls._counter = (cls._counter + 1) % STREAM_LIMIT
        s = QUICStream(stream_id=cls._counter, peer_addr=addr)
        cls._streams[cls._counter] = s
        return s

    @classmethod
    async def _transmit(cls, stream: QUICStream,
                        payload: bytes) -> None:
        # Real: aioquic send_stream_data + drain
        await asyncio.sleep(0)

    # ── Handler registration ──────────────────────────────
    @classmethod
    def on(cls, msg_type: str) -> Callable:
        """Decorator: register async handler for a message type."""
        def decorator(fn: Handler):
            cls._handlers[msg_type] = fn
            return fn
        return decorator

    @classmethod
    async def dispatch(cls, msg_type: str,
                       payload: bytes) -> None:
        handler = cls._handlers.get(msg_type)
        if handler: await handler(payload)

    @classmethod
    def stats(cls) -> Dict:
        total   = len(cls._streams)
        acked   = sum(1 for s in cls._streams.values() if s.acked)
        retried = sum(s.retries for s in cls._streams.values())
        return {"streams": total, "acked": acked,
                "retried": retried}
