from __future__ import annotations
import asyncio, json, os, time
from dataclasses import dataclass, field
from enum        import Enum, auto
from typing      import Any, Dict, List

# Thresholds that trigger a retraining job
AI_CONF_THRESHOLD = 0.70   # below this → collect + retrain
MIN_SAMPLES       = 200   # minimum data points before training
DEPLOY_TIMEOUT    = 30.0  # seconds to wait for edge deploy ACK

class PipelineState(Enum):
    IDLE        = auto()
    COLLECTING  = auto()
    TRAINING    = auto()
    DEPLOYING   = auto()
    DONE        = auto()
    FAILED      = auto()

@dataclass
class TrainingJob:
    job_id:     str
    triggered_by: str            # drone_id that caused the trigger
    state:      PipelineState = PipelineState.IDLE
    samples:    List[Dict]    = field(default_factory=list)
    started_at: float         = field(default_factory=time.time)
    model_path: str           = ""
    metrics:    Dict[str, Any]= field(default_factory=dict)

class RetrainingPipeline:
    """
    Three-stage pipeline: Collect → Train → Deploy.
    Triggered when fleet avg AI confidence drops below threshold.
    Runs async so it never blocks telemetry or WebSocket loops.
    """

    def __init__(self):
        self._jobs:    List[TrainingJob] = []
        self._active:  TrainingJob | None = None
        self._dataset: List[Dict] = []

    # ── Trigger check ─────────────────────────────────────
    def check_trigger(self, drones: List[Dict]) -> bool:
        """Called each telemetry tick; returns True if job was queued."""
        if self._active: return False   # already running
        if not drones:  return False

        avg_conf = sum(d.get("ai_conf", 1.0) for d in drones) / len(drones)
        if avg_conf >= AI_CONF_THRESHOLD:
            return False

        # Find the drone with lowest confidence as trigger source
        worst = min(drones, key=lambda d: d.get("ai_conf", 1.0))
        job = TrainingJob(
            job_id       = f"job-{int(time.time())}",
            triggered_by = worst["id"],
        )
        self._active = job
        self._jobs.append(job)
        asyncio.create_task(self._run_pipeline(job))
        return True

    # ── Pipeline orchestration ────────────────────────────
    async def _run_pipeline(self, job: TrainingJob) -> None:
        try:
            await self._collect(job)
            await self._train(job)
            await self._deploy(job)
            job.state = PipelineState.DONE
        except Exception as e:
            job.state   = PipelineState.FAILED
            job.metrics["error"] = str(e)
        finally:
            self._active = None

    # ── Stage 1: Collect ──────────────────────────────────
    async def _collect(self, job: TrainingJob) -> None:
        """Gather MIN_SAMPLES low-confidence frames from dataset."""
        job.state = PipelineState.COLLECTING
        deadline  = time.monotonic() + 60
        while (len(job.samples) < MIN_SAMPLES
               and time.monotonic() < deadline):
            if self._dataset:
                job.samples.extend(self._dataset)
                self._dataset.clear()
            await asyncio.sleep(1.0)
        job.metrics["samples_collected"] = len(job.samples)

    # ── Stage 2: Train ────────────────────────────────────
    async def _train(self, job: TrainingJob) -> None:
        """Fine-tune TinyML classifier on collected samples."""
        job.state = PipelineState.TRAINING
        t0        = time.monotonic()

        # Real impl: submit to Azure ML / local TFLite training job
        await asyncio.sleep(5.0)   # simulate training duration

        job.model_path = f"/models/tinyml_{job.job_id}.tflite"
        job.metrics["train_time_s"] = round(time.monotonic() - t0, 2)
        job.metrics["val_accuracy"]  = 0.93   # placeholder

    # ── Stage 3: Deploy ───────────────────────────────────
    async def _deploy(self, job: TrainingJob) -> None:
        """Push updated model to all edge nodes; await ACK."""
        job.state = PipelineState.DEPLOYING

        deploy_msg = json.dumps({
            "type":       "model_update",
            "job_id":     job.job_id,
            "model_path": job.model_path,
        }).encode()

        # Broadcast via QUIC to all edge nodes
        from ..networking.quic_transport import QUICTransport
        await asyncio.wait_for(
            QUICTransport.send("edge/broadcast", deploy_msg),
            timeout=DEPLOY_TIMEOUT,
        )
        job.metrics["deployed_at"] = time.time()

    # ── Introspection ─────────────────────────────────────
    def feed(self, frames: List[Dict]) -> None:
        """Add frames to collection buffer (called by TelemetryGenerator)."""
        self._dataset.extend(frames)

    def job_history(self) -> List[Dict]:
        """Return all past and current jobs as dicts."""
        return [
            {
                "jobId":       j.job_id,
                "triggeredBy": j.triggered_by,
                "state":       j.state.name,
                "startedAt":   j.started_at,
                "metrics":     j.metrics,
            }
            for j in reversed(self._jobs)
        ]
