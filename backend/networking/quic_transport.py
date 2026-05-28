from __future__ import annotations
import asyncio, json, time
from typing      import Dict, Optional, Callable, Awaitable
from dataclasses import dataclass, field

# aioquic would be the real dep; simulated here for portability
ACK_TIMEOUT  = 2.0    # seconds before retransmit
MAX_RETRIES  = 3
STREAM_LIMIT = 100    # max concurrent QUIC streams

@dataclass
class QUICStream:
    stream_id:  int
    peer_addr:  str
    created_at: float = field(default_factory=time.monotonic)
    acked:      bool  = False
    retries:    int   = 0

Handler = Callable[[bytes], Awaitable[None]]

class QUICTransport:
    """
    QUIC-based transport layer for inter-drone messaging.
    Features: multiplexed streams, 0-RTT on reconnect,
    per-message ACK with exponential back-off retry.
    Falls back to MQTTFallback if all retries exhausted.
    """

    _streams:  Dict[int, QUICStream] = {}
    _handlers: Dict[str, Handler]   = {}
    _stream_counter = 0

    # ── Send ──────────────────────────────────────────────
    @classmethod
    async def send(cls, addr: str, payload: bytes,
                  msg_type: str = "data") -> bool:
        """
        Open a QUIC stream to addr, transmit payload,
        await ACK. Retries up to MAX_RETRIES with back-off.
        Returns True on success, False after exhausted retries.
        """
        stream = cls._open_stream(addr)

        for attempt in range(MAX_RETRIES):
            try:
                # Simulate QUIC datagram send + ACK wait
                await asyncio.wait_for(
                    cls._transmit(stream, payload),
                    timeout=ACK_TIMEOUT,
                )
                stream.acked = True
                return True

            except asyncio.TimeoutError:
                stream.retries += 1
                backoff = 0.1 * (2 ** attempt)
                await asyncio.sleep(backoff)

        # All retries exhausted — fall back to MQTT
        from .mqtt_fallback import MQTTFallback
        await MQTTFallback.publish(
            topic   = f"swarm/mesh/{addr}",
            payload = payload,
        )
        return False

    # ── Stream management ─────────────────────────────────
    @classmethod
    def _open_stream(cls, addr: str) -> QUICStream:
        cls._stream_counter = (cls._stream_counter + 1) % STREAM_LIMIT
        s = QUICStream(stream_id=cls._stream_counter, peer_addr=addr)
        cls._streams[cls._stream_counter] = s
        return s

    @classmethod
    async def _transmit(cls, stream: QUICStream, payload: bytes) -> None:
        # Real impl: aioquic send_stream_data + drain
        await asyncio.sleep(0)   # yield to event loop

    # ── Handler registration ──────────────────────────────
    @classmethod
    def on(cls, msg_type: str) -> Callable:
        """Decorator: register an async handler for a message type."""
        def decorator(fn: Handler):
            cls._handlers[msg_type] = fn
            return fn
        return decorator

    @classmethod
    async def dispatch(cls, msg_type: str, payload: bytes) -> None:
        """Route an incoming QUIC message to its registered handler."""
        handler = cls._handlers.get(msg_type)
        if handler:
            await handler(payload)

    # ── Diagnostics ───────────────────────────────────────
    @classmethod
    def stats(cls) -> Dict:
        total   = len(cls._streams)
        acked   = sum(1 for s in cls._streams.values() if s.acked)
        retried = sum(s.retries for s in cls._streams.values())
        return {"streams": total, "acked": acked, "retried": retried}
