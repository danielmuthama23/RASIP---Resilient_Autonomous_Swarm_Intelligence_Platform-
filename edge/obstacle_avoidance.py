from __future__ import annotations
from typing import Any, Dict


class ObstacleAvoidance:
    """Simple rule-based obstacle avoidance controller."""

    def plan(self, state: Dict[str, Any], obstacles: Dict[str, Any]) -> Dict[str, Any]:
        """Return a safe movement command based on current state and obstacles."""
        return {
            "velocity_x": 0.0,
            "velocity_y": 0.0,
            "velocity_z": 0.0,
            "heading": state.get("heading", 0.0),
        }
