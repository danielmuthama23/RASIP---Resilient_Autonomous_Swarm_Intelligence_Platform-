from __future__ import annotations
from typing import Dict, Optional


def fallback_position(gps: Dict[str, float], slam: Optional[Dict[str, float]]) -> Dict[str, float]:
    """Return the best available position using GPS and SLAM fallback."""
    if slam:
        return {
            "x": slam.get("x", gps.get("lon", 0.0)),
            "y": slam.get("y", gps.get("lat", 0.0)),
            "z": slam.get("z", 0.0),
        }
    return {
        "x": gps.get("lon", 0.0),
        "y": gps.get("lat", 0.0),
        "z": gps.get("alt", 0.0),
    }
