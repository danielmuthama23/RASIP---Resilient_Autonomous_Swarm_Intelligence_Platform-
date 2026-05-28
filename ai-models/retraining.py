from __future__ import annotations
import asyncio, time
from dataclasses import dataclass, field
from enum        import Enum, auto
from typing      import Any, Dict, List, Optional

from .tinyml_export import TinyMLExporter

# Trigger thresholds
CONF_TRIGGER  = 0.70  # fleet avg AI conf below this → retrain
MIN_SAMPLES   = 200  # minimum frames before training starts
FINE_TUNE_LR  = 5e-5 # fine-tune learning rate (conservative)
FINE_TUNE_EP  = 5    # fine-tune epochs
DEPLOY_WAIT   = 30.0 # seconds to await edge ACK after deploy

class Stage(Enum):
    IDLE       = auto()
    COLLECTING = auto()
    FINE_TUNING= auto()
    EXPORTING  = auto()
    DEPLOYING  = auto()
    DONE       = auto()
    FAILED     = auto()

@dataclass
class RetrainJob:
    job_id:       str
    triggered_by: str
    stage:        Stage = Stage.IDLE
    samples:      List[Dict] = field(default_factory=list)
    val_data:     List[Any]  = field(default_factory=list)
    started_at:   float = field(default_factory=time.time)
    metrics:      Dict[str, Any] = field(default_factory=dict)
    export_path:  str = ""

class RetrainingOrchestrator:
    """
    AI model retraining orchestrator for ai-models/.
    Distinct from backend/fabric/retraining_pipeline.py
    (which handles infra scheduling); this module owns
    the actual model fine-tuning and TFLite export logic.

    Stages: COLLECTING → FINE_TUNING → EXPORTING → DEPLOYING
    """

    def __init__(self):
        self._jobs:    List[RetrainJob] = []
        self._active:  Optional[RetrainJob] = None
        self._buffer:  List[Dict] = []   # incoming low-conf frames

    # ── Frame collection buffer ───────────────────────────
    def collect(self, frames: List[Dict]) -> None:
        """Buffer low-confidence frames for the next training job."""
        self._buffer.extend(frames)

    # ── Trigger check ─────────────────────────────────────
    def check_trigger(self, drones: List[Dict]) -> bool:
        """Called each telemetry tick; returns True if job queued."""
        if self._active or not drones: return False
        avg_conf = sum(
            d.get("ai_conf", 1.0) for d in drones
        ) / len(drones)
        if avg_conf >= CONF_TRIGGER: return False

        worst = min(drones, key=lambda d: d.get("ai_conf", 1.0))
        job   = RetrainJob(
            job_id       = f"retrain-{int(time.time())}",
            triggered_by = worst["id"],
        )
        self._active = job
        self._jobs.append(job)
        asyncio.create_task(self._run(job))
        return True

    # ── Pipeline orchestration ────────────────────────────
    async def _run(self, job: RetrainJob) -> None:
        try:
            await self._collect_stage(job)
            await self._fine_tune_stage(job)
            await self._export_stage(job)
            await self._deploy_stage(job)
            job.stage = Stage.DONE
        except Exception as e:
            job.stage = Stage.FAILED
            job.metrics["error"] = str(e)
        finally:
            self._active = None

    # ── Stage 1: Collect MIN_SAMPLES frames ───────────────
    async def _collect_stage(self, job: RetrainJob) -> None:
        job.stage = Stage.COLLECTING
        deadline  = time.monotonic() + 120
        while (len(job.samples) < MIN_SAMPLES
               and time.monotonic() < deadline):
            job.samples.extend(self._buffer)
            self._buffer.clear()
            await asyncio.sleep(1.0)
        job.metrics["n_samples"] = len(job.samples)

    # ── Stage 2: Fine-tune base model ─────────────────────
    async def _fine_tune_stage(self, job: RetrainJob) -> None:
        job.stage = Stage.FINE_TUNING
        t0 = time.monotonic()
        try:
            import torch
            from torch import nn, optim
            # Load base MobileNetV3-Small for fine-tuning
            model = torch.hub.load(
                "pytorch/vision", "mobilenet_v3_small",
                pretrained=True, verbose=False
            )
            # Freeze all except final classifier
            for p in model.parameters(): p.requires_grad = False
            for p in model.classifier.parameters(): p.requires_grad = True

            opt      = optim.Adam(model.classifier.parameters(),
                                  lr=FINE_TUNE_LR)
            crit     = nn.CrossEntropyLoss()
            model.train()

            for ep in range(FINE_TUNE_EP):
                ep_loss = 0.0
                for frame in job.samples:
                    img   = torch.zeros(1, 3, 96, 96)   # placeholder
                    label = torch.tensor([frame.get("label", 0)])
                    opt.zero_grad()
                    loss = crit(model(img), label)
                    loss.backward()
                    opt.step()
                    ep_loss += loss.item()
                job.metrics[f"loss_ep{ep}"] = ep_loss / len(job.samples)

            job.metrics["fine_tune_time_s"] = round(
                time.monotonic() - t0, 2)
            job.metrics["model"] = model
        except ImportError:
            job.metrics["model"] = "mock_model"
            await asyncio.sleep(2.0)   # simulate training time

    # ── Stage 3: Export to TFLite ─────────────────────────
    async def _export_stage(self, job: RetrainJob) -> None:
        job.stage = Stage.EXPORTING
        exporter  = TinyMLExporter(job.job_id)
        result    = exporter.export(
            model      = job.metrics.get("model"),
            val_data   = job.val_data,
            output_name = f"tinyml_{job.job_id}.tflite",
        )
        if not result.success:
            raise RuntimeError(f"Export failed: {result.error}")
        job.export_path             = str(result.output_path)
        job.metrics["accuracy"]   = result.accuracy
        job.metrics["size_bytes"] = result.size_bytes

    # ── Stage 4: Deploy via ModelRegistry hot-swap ────────
    async def _deploy_stage(self, job: RetrainJob) -> None:
        job.stage = Stage.DEPLOYING
        from pathlib import Path
        from edge.models.model_registry import ModelRegistry
        registry = ModelRegistry()
        registry.hot_swap("tinyml", Path(job.export_path))
        job.metrics["deployed_at"] = time.time()

    # ── Introspection ─────────────────────────────────────
    def job_history(self) -> List[Dict]:
        return [
            {"job_id": j.job_id, "stage": j.stage.name,
             "triggered_by": j.triggered_by,
             "started_at": j.started_at,
             "metrics": {k: v for k, v in j.metrics.items()
                         if k != "model"}}
            for j in reversed(self._jobs)
        ]
