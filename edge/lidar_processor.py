from __future__ import annotations
from typing import Any, Dict, List


class LidarProcessor:
    """Edge-side LiDAR processor for obstacle and range detection."""

    def __init__(self) -> None:
        self.scan_history: List[Dict[str, Any]] = []

    def process_scan(self, scan: bytes) -> Dict[str, Any]:
        """Convert a raw lidar scan payload into obstacle metrics."""
        result = {
            "closest_distance": float("inf"),
            "obstacle_count": 0,
        }
        return result
