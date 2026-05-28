import numpy as np
from dataclasses import dataclass
from typing      import List, Optional

@dataclass
class Waypoint:
    lat:    float
    lon:    float
    alt:    float
    radius: float = 5.0   # acceptance radius in metres

class Navigator:
    """
    Waypoint sequencer for a single drone.
    Position source falls back: GPS → SLAM → swarm-relative.
    """

    def __init__(self, drone_id: str):
        self.drone_id  = drone_id
        self.waypoints: List[Waypoint] = []
        self._idx      = 0
        self._gps_ok   = True

    # ── Mission loading ───────────────────────────────────
    def load_mission(self, wps: List[Waypoint]) -> None:
        self.waypoints = wps
        self._idx      = 0

    def current_wp(self) -> Optional[Waypoint]:
        return self.waypoints[self._idx] if self._idx < len(self.waypoints) else None

    def advance(self) -> None:
        self._idx = min(self._idx + 1, len(self.waypoints))

    # ── Position fallback chain ───────────────────────────
    def position(self, drone) -> np.ndarray:
        if drone.signal > 40:
            self._gps_ok = True
            return np.array([drone.x, drone.y, drone.altitude])
        if getattr(drone, "slam_x", None) is not None:
            self._gps_ok = False
            return np.array([drone.slam_x, drone.slam_y, drone.slam_z])
        # Last resort: swarm-relative from nearest neighbour
        return np.array([
            getattr(drone, "rel_x", 0.0),
            getattr(drone, "rel_y", 0.0),
            getattr(drone, "rel_z", 50.0),
        ])

    # ── Steering vector ───────────────────────────────────
    def steer(self, drone) -> np.ndarray:
        """Return unit vector toward current waypoint; advance when close."""
        wp = self.current_wp()
        if wp is None:
            return np.zeros(3)

        pos    = self.position(drone)
        target = np.array([wp.lat, wp.lon, wp.alt])
        delta  = target - pos
        dist   = np.linalg.norm(delta)

        if dist < wp.radius:
            self.advance()
            return np.zeros(3)

        return delta / (dist + 1e-8)   # unit steering vector

    # ── Status ────────────────────────────────────────────
    def status(self) -> dict:
        return {
            "drone_id":      self.drone_id,
            "waypoint_idx":  self._idx,
            "total_wps":     len(self.waypoints),
            "gps_ok":        self._gps_ok,
            "current_wp":    self.current_wp().__dict__ if self.current_wp() else None,
        }
