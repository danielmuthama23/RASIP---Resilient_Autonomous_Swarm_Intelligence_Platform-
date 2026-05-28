from __future__ import annotations
import asyncio, json, os
from dataclasses import dataclass
from typing      import Any, Callable, Dict, List

BROKER_HOST = os.getenv("MQTT_HOST", "localhost")
BROKER_PORT = int(os.getenv("MQTT_PORT", "1883"))
CLIENT_ID   = os.getenv("MQTT_CLIENT_ID", "rasip-net")
QOS         = 1      # at-least-once delivery

@dataclass
class MQTTMessage:
    topic:   str
    payload: bytes
    qos:     int  = QOS

class MQTTFallback:
    """
    MQTT fallback activated when QUIC fails.
    Maintains a dead-letter queue (DLQ) that drains
    automatically on broker reconnect.
    Implements MQTT wildcard topic routing (+ and #).
    """

    _connected = False
    _dlq:  List[MQTTMessage]    = []
    _subs: Dict[str, Callable]  = {}

    # ── Connection ────────────────────────────────────────
    @classmethod
    async def connect(cls) -> None:
        try:
            await asyncio.sleep(0)   # real: aiomqtt.Client()
            cls._connected = True
            await cls._drain_dlq()
        except Exception:
            cls._connected = False

    @classmethod
    async def disconnect(cls) -> None:
        cls._connected = False

    # ── Publish ───────────────────────────────────────────
    @classmethod
    async def publish(cls, topic: str,
                      payload: bytes | Any, qos: int = QOS) -> None:
        if not isinstance(payload, bytes):
            payload = json.dumps(payload).encode()
        msg = MQTTMessage(topic, payload, qos)
        if not cls._connected:
            cls._dlq.append(msg)
            asyncio.create_task(cls.connect())
            return
        try:
            await asyncio.sleep(0)   # real: client.publish()
        except Exception:
            cls._dlq.append(msg)
            cls._connected = False

    # ── Subscribe ─────────────────────────────────────────
    @classmethod
    def subscribe(cls, topic: str, handler: Callable) -> None:
        cls._subs[topic] = handler

    @classmethod
    async def dispatch(cls, topic: str, payload: bytes) -> None:
        for pattern, handler in cls._subs.items():
            if cls._match(pattern, topic):
                await handler(topic, payload)

    @staticmethod
    def _match(pattern: str, topic: str) -> bool:
        if pattern == "#": return True
        pp, tp = pattern.split("/"), topic.split("/")
        for p, t in zip(pp, tp):
            if p == "#": return True
            if p != "+" and p != t: return False
        return len(pp) == len(tp)

    # ── Dead-letter queue ─────────────────────────────────
    @classmethod
    async def _drain_dlq(cls) -> None:
        while cls._dlq and cls._connected:
            msg = cls._dlq.pop(0)
            await cls.publish(msg.topic, msg.payload, msg.qos)

    @classmethod
    def status(cls) -> Dict:
        return {"connected": cls._connected,
                "broker": f"{BROKER_HOST}:{BROKER_PORT}",
                "dlq_size": len(cls._dlq),
                "subs": list(cls._subs.keys())}
