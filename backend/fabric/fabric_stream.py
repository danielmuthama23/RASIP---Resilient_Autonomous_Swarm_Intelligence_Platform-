from __future__ import annotations
import asyncio, json, os, time
from typing      import Any, Dict, List
from dataclasses import dataclass, field

# azure-eventhub would be the real dep
CONN_STR    = os.getenv("AZURE_EVENTHUB_CONN_STR", "")
HUB_NAME    = os.getenv("AZURE_EVENTHUB_NAME", "rasip-telemetry")
BATCH_SIZE  = 50     # frames per EventData batch
FLUSH_EVERY = 5.0   # seconds — max time before forced flush

@dataclass
class TelemetryFrame:
    drone_id:  str
    timestamp: float
    battery:   float
    signal:    float
    ai_conf:   float
    x: float;  y: float;  z: float
    formation: str
    alert:     bool
    extras:    Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "droneId":   self.drone_id,
            "ts":        self.timestamp,
            "battery":   self.battery,
            "signal":    self.signal,
            "aiConf":    self.ai_conf,
            "pos":       {"x": self.x, "y": self.y, "z": self.z},
            "formation": self.formation,
            "alert":     self.alert,
            **self.extras,
        }

class FabricStream:
    """
    Async Azure Event Hub producer.
    Accumulates TelemetryFrames in a buffer; flushes when
    BATCH_SIZE is reached or FLUSH_EVERY seconds elapse.
    On send failure, frames are re-queued (at-least-once).
    """

    def __init__(self):
        self._buffer:   List[TelemetryFrame] = []
        self._last_flush = time.monotonic()
        self._sent_total = 0
        self._err_total  = 0
        self._summary:  Dict = {}

    # ── Main run loop ─────────────────────────────────────
    async def run(self) -> None:
        """Background task: flush buffer on size or time trigger."""
        while True:
            await asyncio.sleep(0.5)
            elapsed = time.monotonic() - self._last_flush
            if (len(self._buffer) >= BATCH_SIZE
                    or elapsed >= FLUSH_EVERY):
                await self.flush()

    # ── Ingest a drone telemetry snapshot ─────────────────
    def ingest(self, drones: List[Dict]) -> None:
        """Called from TelemetryGenerator each tick."""
        ts = time.time()
        mission = ""  # injected by caller in production
        for d in drones:
            self._buffer.append(TelemetryFrame(
                drone_id  = d["id"],
                timestamp = ts,
                battery   = d.get("battery", 0),
                signal    = d.get("signal",  0),
                ai_conf   = d.get("ai_conf", 0),
                x = d.get("x", 0), y = d.get("y", 0),
                z = d.get("altitude", 0),
                formation = mission,
                alert     = d.get("alert", False),
            ))

    # ── Flush buffer to Event Hub ─────────────────────────
    async def flush(self) -> None:
        """Send buffered frames to Azure Event Hub in one batch."""
        if not self._buffer: return
        batch, self._buffer = self._buffer[:BATCH_SIZE], self._buffer[BATCH_SIZE:]
        self._last_flush = time.monotonic()

        events = [json.dumps(f.to_dict()).encode() for f in batch]
        try:
            # Real: async with EventHubProducerClient.from_connection_string()
            #           as client: await client.send_batch(event_data_batch)
            await asyncio.sleep(0)   # yield — real send here
            self._sent_total += len(batch)
            self._update_summary(batch)
        except Exception:
            # Re-queue failed frames at the front for retry
            self._buffer = batch + self._buffer
            self._err_total += 1

    # ── Rolling summary for /analytics endpoint ───────────
    def _update_summary(self, batch: List[TelemetryFrame]) -> None:
        if not batch: return
        self._summary = {
            "sent_total":  self._sent_total,
            "err_total":   self._err_total,
            "buffer_len":  len(self._buffer),
            "avg_battery": sum(f.battery for f in batch) / len(batch),
            "avg_signal":  sum(f.signal  for f in batch) / len(batch),
            "alerts":      sum(1 for f in batch if f.alert),
        }

    def summary(self) -> Dict:
        """Return latest batch summary for GET /analytics."""
        return self._summary
