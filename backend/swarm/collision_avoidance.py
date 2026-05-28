import numpy as np
from dataclasses import dataclass, field
from typing      import List

SAFE_DIST  = 5.0   # metres — minimum safe separation
EVADE_GAIN = 8.0   # repulsion scale factor

@dataclass
class Obstacle:
    pos:    np.ndarray
    radius: float = 2.0     # obstacle radius (m)
    source: str   = "lidar" # lidar | radar | fusion

class CollisionAvoidance:
    """
    Fuses LiDAR and radar obstacle reports into a single
    repulsion vector. If distance < SAFE_DIST the drone
    reroutes immediately (logs to MCP + AI insights).
    """

    def __init__(self):
        self._obstacles: List[Obstacle] = []

    # ── Obstacle ingestion ───────────────────────────────
    def update_lidar(self, points: np.ndarray):
        """Accept (N, 3) point cloud; cluster into obstacles."""
        if points.size == 0: return
        # Simplified: treat each point as a small obstacle
        self._obstacles = [
            Obstacle(pos=p, radius=1.5, source="lidar")
            for p in points
        ]

    def update_radar(self, detections: List[dict]):
        """Accept radar detections [{pos, radius}, …]."""
        for d in detections:
            self._obstacles.append(
                Obstacle(
                    pos    = np.array(d["pos"]),
                    radius = d.get("radius", 3.0),
                    source = "radar",
                )
            )

    # ── Repulsion steering ───────────────────────────────
    def steer(self, boid) -> np.ndarray:
        """Return avoidance acceleration vector for one boid."""
        acc = np.zeros(3)
        for obs in self._obstacles:
            delta = boid.pos - obs.pos
            dist  = np.linalg.norm(delta)
            threshold = SAFE_DIST + obs.radius

            if 0 < dist < threshold:
                # Exponential repulsion: stronger the closer we get
                strength = EVADE_GAIN * np.exp(-(dist - obs.radius))
                acc += (delta / dist) * strength
                boid.alert = True

        return acc

    # ── Hard reroute check ───────────────────────────────
    def needs_reroute(self, boid) -> bool:
        """True when any obstacle is within strict SAFE_DIST."""
        for obs in self._obstacles:
            if np.linalg.norm(boid.pos - obs.pos) < SAFE_DIST:
                return True
        return False

    # ── Fusion: merge lidar + radar obstacle lists ────────
    def fuse(self):
        """De-duplicate obstacles from multiple sensors (distance threshold)."""
        fused = []
        for obs in self._obstacles:
            merged = False
            for f in fused:
                if np.linalg.norm(obs.pos - f.pos) < 3.0:
                    # Weighted average of positions
                    f.pos = (f.pos + obs.pos) / 2
                    f.source = "fusion"
                    merged = True
                    break
            if not merged:
                fused.append(obs)
        self._obstacles = fused
