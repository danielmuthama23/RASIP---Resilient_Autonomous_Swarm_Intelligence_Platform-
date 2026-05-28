from __future__ import annotations
import asyncio, os, json
from typing      import Any, Callable, Dict, List
from dataclasses import dataclass

# aiomqtt / paho-mqtt would be the real dep
BROKER_HOST  = os.getenv("MQTT_HOST", "localhost")
BROKER_PORT  = int(os.getenv("MQTT_PORT", "1883"))
CLIENT_ID    = os.getenv("MQTT_CLIENT_ID", "rasip-backend")
QOS          = 1     # at-least-once delivery
RETAIN       = False

@dataclass
class MQTTMessage:
    topic:   str
    payload: bytes
    qos:     int  = QOS
    retain:  bool = RETAIN

class MQTTFallback:
    """
    IoT MQTT fallback activated when QUIC fails.
    Supports publish, subscribe, and a dead-letter queue
    that retries messages when the broker reconnects.
    """

    _connected:  bool           = False
    _dlq:        List[MQTTMessage] = []   # dead-letter queue
    _subs:       Dict[str, Callable] = {}

    # ── Connection ────────────────────────────────────────
    @classmethod
    async def connect(cls) -> None:
        """Establish MQTT connection; drain DLQ on success."""
        try:
            # Real impl: await aiomqtt.Client(BROKER_HOST, BROKER_PORT)
            await asyncio.sleep(0)
            cls._connected = True
            await cls._drain_dlq()
        except Exception as e:
            cls._connected = False

    @classmethod
    async def disconnect(cls) -> None:
        cls._connected = False

    # ── Publish ───────────────────────────────────────────
    @classmethod
    async def publish(cls, topic: str, payload: bytes | Any,
                      qos: int = QOS) -> None:
        """
        Publish to broker. If not connected, enqueue to DLQ.
        Payload auto-serialised if not bytes.
        """
        if not isinstance(payload, bytes):
            payload = json.dumps(payload).encode()

        msg = MQTTMessage(topic=topic, payload=payload, qos=qos)

        if not cls._connected:
            cls._dlq.append(msg)
            asyncio.create_task(cls.connect())   # try reconnect
            return

        try:
            # Real impl: await client.publish(topic, payload, qos)
            await asyncio.sleep(0)
        except Exception:
            cls._dlq.append(msg)
            cls._connected = False

    # ── Subscribe ─────────────────────────────────────────
    @classmethod
    def subscribe(cls, topic: str, handler: Callable) -> None:
        """Register a callback for an MQTT topic pattern."""
        cls._subs[topic] = handler

    @classmethod
    async def dispatch(cls, topic: str, payload: bytes) -> None:
        """Route incoming MQTT message to matching subscriber."""
        for pattern, handler in cls._subs.items():
            if cls._topic_match(pattern, topic):
                await handler(topic, payload)

    @staticmethod
    def _topic_match(pattern: str, topic: str) -> bool:
        """Simple MQTT wildcard matching: # and +."""
        if pattern == "#": return True
        p_parts = pattern.split("/")
        t_parts = topic.split("/")
        for p, t in zip(p_parts, t_parts):
            if p == "#": return True
            if p != "+" and p != t: return False
        return len(p_parts) == len(t_parts)

    # ── Dead-letter queue ─────────────────────────────────
    @classmethod
    async def _drain_dlq(cls) -> None:
        """Replay queued messages after broker reconnects."""
        while cls._dlq and cls._connected:
            msg = cls._dlq.pop(0)
            await cls.publish(msg.topic, msg.payload, msg.qos)

    @classmethod
    def dlq_size(cls) -> int:
        return len(cls._dlq)

    @classmethod
    def status(cls) -> Dict:
        return {
            "connected": cls._connected,
            "broker":    f"{BROKER_HOST}:{BROKER_PORT}",
            "dlq_size":  cls.dlq_size(),
            "subs":      list(cls._subs.keys()),
        }
