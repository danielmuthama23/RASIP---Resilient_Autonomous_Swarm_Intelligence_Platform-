from __future__ import annotations
import asyncio, time, random
from dataclasses import dataclass, field
from typing      import TYPE_CHECKING

if TYPE_CHECKING:
    from .swarm.boids_engine import BoidsEngine
    from .mcp_context        import MCPContextEngine

from .sensor_fusion            import SensorFusion
from .websocket_server         import broadcast
from .security.hedera_identity import HederaIdentity

TICK_HZ  = 10   # telemetry frames per second
HIST_LEN = 50   # rolling history length per drone

@dataclass
class DroneState:
    id:       str
    x:        float = 0.0
    y:        float = 0.0
    altitude: float = 50.0
    heading:  float = 0.0
    battery:  float = 100.0
    signal:   float = 100.0
    ai_conf:  float = 0.9
    alert:    bool  = False
    lat:      float = -1.2921   # Nairobi default
    lon:      float = 36.8219
    history:  list  = field(default_factory=list)

class TelemetryGenerator:
    def __init__(self, boids: 'BoidsEngine', mcp: 'MCPContextEngine'):
        self.boids  = boids
        self.mcp    = mcp
        self.fusion = SensorFusion()
        self.hedera = HederaIdentity()

    async def run(self) -> None:
        """Emit telemetry at TICK_HZ; broadcast via WebSocket."""
        while True:
            t0     = time.monotonic()
            drones = []

            for boid in self.boids.drones:
                # Fuse GPS + IMU + SLAM → smoothed position
                pos = self.fusion.fuse(boid)

                # Drain battery, add signal noise
                boid.battery = max(0.0, boid.battery
                    - random.uniform(0.001, 0.003))
                boid.signal  = max(0.0, 100.0
                    - random.gauss(5, 2))

                # SHA-256 sign each frame via Hedera ledger
                frame = {"id": boid.id, "pos": pos, "bat": boid.battery}
                self.hedera.sign(boid.id, frame)

                # Append to rolling 50-frame history
                boid.history = (boid.history + [pos])[-HIST_LEN:]

                drones.append({
                    "id":       boid.id,
                    "x":        pos["x"],   "y": pos["y"],
                    "altitude": pos["z"],
                    "heading":  boid.heading,
                    "battery":  boid.battery,
                    "signal":   boid.signal,
                    "ai_conf":  boid.ai_conf,
                    "alert":    boid.alert,
                    "lat":      -1.2921 + pos["x"] / 111_000,
                    "lon":      36.8219 + pos["y"] / 111_000,
                    "history":  boid.history,
                })

            self.mcp.update(drones)
            await broadcast({"type": "telemetry", "drones": drones})

            elapsed = time.monotonic() - t0
            await asyncio.sleep(max(0.0, 1.0 / TICK_HZ - elapsed))
