from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List


class YOLODetector:
    """Lightweight edge-facing YOLO detection wrapper."""

    def __init__(self, weights: Path) -> None:
        self.weights = weights
        self.model = self._load_model(weights)

    def _load_model(self, weights: Path) -> Any:
        try:
            from ultralytics import YOLO
            return YOLO(str(weights))
        except ImportError:
            return None

    def detect(self, image: bytes) -> List[Dict[str, Any]]:
        """Run detection on a raw image payload."""
        if self.model is None:
            return []
        results = self.model(image)
        return [r.boxes.xyxy.tolist() for r in results]
