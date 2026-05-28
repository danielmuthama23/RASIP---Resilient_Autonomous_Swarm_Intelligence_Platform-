from __future__ import annotations
import hashlib, os, time
from dataclasses import dataclass, field
from pathlib    import Path
from threading  import Lock
from typing     import Any, Dict, Optional

MODEL_DIR = Path(__file__).parent

# Known model manifest: name → {file, sha256_prefix, loader}
MANIFEST: Dict[str, Dict] = {
    "yolov8n": {
        "file":   "yolov8n.pt",
        "sha256": "980164",   # first 6 hex chars of expected hash
        "type":   "pytorch",
        "params": "3.2M",
        "task":   "detection",
    },
    "tinyml": {
        "file":   "tinyml_classifier.tflite",
        "sha256": "e839c4",
        "type":   "tflite",
        "params": "220K",
        "task":   "classification",
    },
}

@dataclass
class ModelHandle:
    name:       str
    model:      Any              # loaded model object
    path:       Path
    loaded_at:  float = field(default_factory=time.time)
    checksum:   str   = ""
    valid:      bool  = True

class ModelRegistry:
    """
    Central model registry for edge inference.
    Responsibilities:
      • Verify SHA-256 checksums on load
      • Cache loaded model objects
      • Hot-swap weights without process restart
      • Expose metadata for the retraining pipeline
    """

    def __init__(self):
        self._cache: Dict[str, ModelHandle] = {}
        self._lock  = Lock()

    # ── Load a model by name ──────────────────────────────
    def load(self, name: str,
             force_reload: bool = False) -> ModelHandle:
        """
        Load and cache a model. Validates SHA-256 checksum.
        If already cached and force_reload=False, returns cache.
        """
        with self._lock:
            if name in self._cache and not force_reload:
                return self._cache[name]

        meta = MANIFEST.get(name)
        if not meta:
            raise KeyError(f"Unknown model: '{name}'")

        path = MODEL_DIR / meta["file"]
        if not path.exists():
            raise FileNotFoundError(f"Model file missing: {path}")

        # Verify checksum
        checksum = self._sha256(path)
        valid    = checksum.startswith(meta["sha256"])

        # Load model object
        model = self._load_model(meta["type"], path)

        handle = ModelHandle(
            name=name, model=model,
            path=path, checksum=checksum, valid=valid,
        )
        with self._lock:
            self._cache[name] = handle
        return handle

    # ── Hot-swap: load new weights without restart ─────────
    def hot_swap(self, name: str, new_path: Path) -> ModelHandle:
        """
        Replace the weights file at models/ and reload.
        Called by RetrainingPipeline after deploy ACK.
        """
        dest = MODEL_DIR / MANIFEST[name]["file"]
        import shutil
        shutil.copy2(new_path, dest)
        return self.load(name, force_reload=True)

    # ── Type-specific loader ───────────────────────────────
    def _load_model(self, model_type: str, path: Path) -> Any:
        if model_type == "pytorch":
            try:
                from ultralytics import YOLO
                return YOLO(str(path))
            except ImportError:
                return "mock_yolo"

        if model_type == "tflite":
            try:
                import tflite_runtime.interpreter as tflite
                interp = tflite.Interpreter(str(path))
                interp.allocate_tensors()
                return interp
            except ImportError:
                return "mock_tflite"

        raise ValueError(f"Unknown model type: {model_type}")

    # ── SHA-256 checksum ──────────────────────────────────
    @staticmethod
    def _sha256(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    # ── Introspection ─────────────────────────────────────
    def list_models(self) -> Dict[str, Dict]:
        """Return manifest + cache status for all known models."""
        with self._lock:
            cached = set(self._cache.keys())
        return {
            name: {
                **meta,
                "cached":  name in cached,
                "on_disk": (MODEL_DIR / meta["file"]).exists(),
            }
            for name, meta in MANIFEST.items()
        }

    def get(self, name: str) -> Optional[ModelHandle]:
        """Return cached handle if loaded, else None."""
        with self._lock:
            return self._cache.get(name)

    def invalidate(self, name: str) -> None:
        """Evict a model from cache (forces reload on next access)."""
        with self._lock:
            self._cache.pop(name, None)
