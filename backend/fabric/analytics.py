from __future__ import annotations
import statistics, time
from collections  import defaultdict, deque
from dataclasses  import dataclass
from typing       import Dict, List, Optional

WINDOW_SEC  = 300    # 5-minute sliding window
Z_THRESHOLD = 2.0   # anomaly if |z-score| > 2σ
MIN_SAMPLES = 10    # need at least this many points to score

@dataclass
class AnomalyReport:
    drone_id:    str
    metric:      str
    value:       float
    mean:        float
    stdev:       float
    z_score:     float
    detected_at: float

class SwarmAnalytics:
    """
    In-process KQL-style analytics engine.
    Maintains per-drone sliding windows for battery, signal,
    and ai_conf. Raises AnomalyReport when z-score > 2σ.
    """

    def __init__(self):
        # {drone_id: {metric: deque[(ts, value)]}} 
        self._windows: Dict[str, Dict[str, deque]] = defaultdict(
            lambda: {"battery": deque(), "signal": deque(), "ai_conf": deque()}
        )
        self._anomalies: List[AnomalyReport] = []

    # ── Ingest a snapshot ─────────────────────────────────
    def ingest(self, drones: List[Dict]) -> List[AnomalyReport]:
        """
        Feed latest drone telemetry; return any new anomalies
        detected in this batch.
        """
        now    = time.time()
        alerts = []
        for d in drones:
            did = d["id"]
            for metric in ("battery", "signal", "ai_conf"):
                val = d.get(metric)
                if val is None: continue

                win = self._windows[did][metric]
                win.append((now, val))

                # Evict samples older than WINDOW_SEC
                while win and now - win[0][0] > WINDOW_SEC:
                    win.popleft()

                report = self._check_anomaly(did, metric, val, win)
                if report:
                    alerts.append(report)
                    self._anomalies.append(report)

        return alerts

    # ── Anomaly detection ─────────────────────────────────
    def _check_anomaly(
        self, drone_id: str, metric: str,
        value: float, win: deque
    ) -> Optional[AnomalyReport]:
        if len(win) < MIN_SAMPLES:
            return None

        vals  = [v for _, v in win]
        mean  = statistics.mean(vals)
        stdev = statistics.stdev(vals)

        if stdev < 1e-6:
            return None   # all values identical — no anomaly

        z = (value - mean) / stdev
        if abs(z) < Z_THRESHOLD:
            return None

        return AnomalyReport(
            drone_id    = drone_id,
            metric      = metric,
            value       = value,
            mean        = mean,
            stdev       = stdev,
            z_score     = z,
            detected_at = time.time(),
        )

    # ── Fleet-level aggregates ────────────────────────────
    def fleet_summary(self) -> Dict:
        """Return current mean + stdev per metric across all drones."""
        out: Dict[str, Dict] = {}
        for metric in ("battery", "signal", "ai_conf"):
            all_vals = [
                win[metric][-1][1]
                for win in self._windows.values()
                if win[metric]
            ]
            if not all_vals:
                continue
            out[metric] = {
                "mean":  statistics.mean(all_vals),
                "stdev": statistics.stdev(all_vals) if len(all_vals) > 1 else 0.0,
                "n":     len(all_vals),
            }
        return out

    def recent_anomalies(self, limit: int = 20) -> List[Dict]:
        """Return the most recent anomaly reports as dicts."""
        return [
            {
                "droneId":    a.drone_id,
                "metric":     a.metric,
                "value":      round(a.value,  2),
                "mean":       round(a.mean,   2),
                "stdev":      round(a.stdev,  2),
                "zScore":     round(a.z_score, 2),
                "detectedAt": a.detected_at,
            }
            for a in reversed(self._anomalies[-limit:])
        ]
