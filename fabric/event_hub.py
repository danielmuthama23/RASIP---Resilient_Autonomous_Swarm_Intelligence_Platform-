from __future__ import annotations
import asyncio, json, os, time
from dataclasses import dataclass, field
from typing      import Any, Dict, List

# azure-eventhub — installed as core dep
CONN_STR    = os.getenv("AZURE_EVENTHUB_CONN_STR", "")
HUB_NAME    = os.getenv("AZURE_EVENTHUB_NAME", "rasip-telemetry")
BATCH_SIZE  = 100    # events per EventData batch
FLUSH_EVERY = 10.0  # seconds — max time before forced flush
MAX_RETRIES = 3

@dataclass
class TelemetryEvent:
    drone_id:  str
    ts:        float
    battery:   float
    signal:    float
    ai_conf:   float
    x: float; y: float; z: float
    formation: str
    alert:     bool
    extras:    Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({
            "droneId":   self.drone_id,
            "ts":        self.ts,
            "battery":   self.battery,
            "signal":    self.signal,
            "aiConf":    self.ai_conf,
            "pos":       {"x": self.x, "y": self.y, "z": self.z},
            "formation": self.formation,
            "alert":     self.alert,
            **self.extras,
        })

class EventHubProducer:
    """
    Top-level Azure Event Hub async producer.
    Buffers TelemetryEvents; flushes when BATCH_SIZE
    is reached or FLUSH_EVERY seconds elapse.
    Failed batches are re-queued (at-least-once delivery).
    """

    def __init__(self):
        self._buffer:    List[TelemetryEvent] = []
        self._last_flush = time.monotonic()
        self._sent       = 0
        self._errors     = 0
        self._onelake    = None   # injected after init

    # ── Ingest drone snapshots ────────────────────────────
    def ingest(self, drones: List[Dict],
              formation: str = "") -> None:
        ts = time.time()
        for d in drones:
            self._buffer.append(TelemetryEvent(
                drone_id  = d["id"],
                ts        = ts,
                battery   = d.get("battery",  0),
                signal    = d.get("signal",   0),
                ai_conf   = d.get("ai_conf",  0),
                x = d.get("x", 0),
                y = d.get("y", 0),
                z = d.get("altitude", 0),
                formation = formation,
                alert     = d.get("alert", False),
            ))

    # ── Background flush loop ─────────────────────────────
    async def run(self) -> None:
        while True:
            await asyncio.sleep(0.5)
            elapsed = time.monotonic() - self._last_flush
            if (len(self._buffer) >= BATCH_SIZE
                    or elapsed >= FLUSH_EVERY):
                await self.flush()

    # ── Flush buffer to Event Hub ─────────────────────────
    async def flush(self) -> None:
        if not self._buffer: return
        batch, self._buffer = (
            self._buffer[:BATCH_SIZE],
            self._buffer[BATCH_SIZE:]
        )
        self._last_flush = time.monotonic()

        for attempt in range(MAX_RETRIES):
            try:
                await self._send_batch(batch)
                self._sent += len(batch)
                if self._onelake:
                    await self._onelake.append(batch)
                return
            except Exception:
                await asyncio.sleep(0.5 * (2 ** attempt))

        # Re-queue on exhausted retries
        self._buffer = batch + self._buffer
        self._errors += 1

    async def _send_batch(self, batch: List[TelemetryEvent]) -> None:
        if not CONN_STR:
            await asyncio.sleep(0)   # dev stub
            return
        try:
            from azure.eventhub.aio import EventHubProducerClient
            from azure.eventhub       import EventData
            async with EventHubProducerClient.from_connection_string(
                CONN_STR, eventhub_name=HUB_NAME
            ) as client:
                eb = await client.create_batch()
                for ev in batch:
                    eb.add(EventData(ev.to_json()))
                await client.send_batch(eb)
        except ImportError:
            await asyncio.sleep(0)   # azure-eventhub not installed

    def stats(self) -> Dict:
        return {"sent": self._sent, "errors": self._errors,
                "buffer_len": len(self._buffer)}
