from __future__ import annotations
import statistics, time
from collections  import defaultdict, deque
from dataclasses  import dataclass
from typing       import Any, Dict, List, Optional

# Remote KQL endpoint (Microsoft Fabric Eventhouse)
import os
KQL_ENDPOINT = os.getenv("FABRIC_KQL_ENDPOINT", "")
KQL_DB       = os.getenv("FABRIC_KQL_DB", "rasip")

# In-process sliding window parameters
WINDOW_SEC  = 300    # 5-minute window
Z_THRESHOLD = 2.0   # anomaly if |z| > 2σ
MIN_SAMPLES = 10

@dataclass
class Anomaly:
    drone_id:    str
    metric:      str
    value:       float
    mean:        float
    stdev:       float
    z_score:     float
    detected_at: float

class KQLAnalytics:
    """
    Hybrid analytics: in-process sliding windows for
    real-time anomaly detection, plus remote KQL queries
    against the Fabric Eventhouse for historical analysis.
    """

    def __init__(self):
        self._windows: Dict[str, Dict[str, deque]] = defaultdict(
            lambda: {m: deque() for m in ("battery", "signal", "ai_conf")}
        )
        self._anomalies: List[Anomaly] = []

    # ── Real-time ingest and anomaly detection ────────────
    def ingest(self, drones: List[Dict]) -> List[Anomaly]:
        """Feed latest telemetry; return new anomalies."""
        now, alerts = time.time(), []
        for d in drones:
            did = d["id"]
            for metric in ("battery", "signal", "ai_conf"):
                val = d.get(metric)
                if val is None: continue
                win = self._windows[did][metric]
                win.append((now, val))
                while win and now - win[0][0] > WINDOW_SEC:
                    win.popleft()
                a = self._detect(did, metric, val, win)
                if a:
                    alerts.append(a)
                    self._anomalies.append(a)
        return alerts

    def _detect(self, did: str, metric: str,
               val: float, win: deque) -> Optional[Anomaly]:
        if len(win) < MIN_SAMPLES: return None
        vals  = [v for _, v in win]
        mean  = statistics.mean(vals)
        stdev = statistics.stdev(vals)
        if stdev < 1e-6: return None
        z = (val - mean) / stdev
        if abs(z) < Z_THRESHOLD: return None
        return Anomaly(drone_id=did, metric=metric,
                      value=val, mean=mean, stdev=stdev,
                      z_score=z, detected_at=time.time())

    # ── Remote KQL queries against Fabric Eventhouse ──────
    async def kql_query(self, query: str) -> List[Dict]:
        """Execute a KQL query against Fabric Eventhouse."""
        if not KQL_ENDPOINT:
            return []   # dev: no remote endpoint configured
        try:
            from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
            kcsb   = KustoConnectionStringBuilder.with_aad_device_authentication(
                KQL_ENDPOINT)
            client = KustoClient(kcsb)
            resp   = client.execute(KQL_DB, query)
            cols   = [c.column_name for c in
                      resp.primary_results[0].columns]
            return [dict(zip(cols, row))
                    for row in resp.primary_results[0].rows]
        except ImportError:
            return []

    # ── Canned KQL queries ────────────────────────────────
    async def battery_trend(self, window_min: int = 60) -> List[Dict]:
        return await self.kql_query(f"""
            SwarmTelemetry
            | where TimeGenerated > ago({window_min}m)
            | summarize avg_battery = avg(battery)
              by bin(TimeGenerated, 1m), droneId
            | order by TimeGenerated desc
        """)

    async def alert_summary(self, window_min: int = 10) -> List[Dict]:
        return await self.kql_query(f"""
            SwarmTelemetry
            | where TimeGenerated > ago({window_min}m)
              and alert == true
            | summarize alert_count = count() by droneId
            | order by alert_count desc
        """)

    async def fleet_summary(self) -> List[Dict]:
        return await self.kql_query("""
            SwarmTelemetry
            | summarize
                avg_battery = avg(battery),
                avg_signal  = avg(signal),
                avg_ai_conf = avg(aiConf),
                events      = count()
              by bin(TimeGenerated, 1m)
            | order by TimeGenerated desc
            | take 50
        """)

    # ── Introspection ─────────────────────────────────────
    def recent_anomalies(self, n: int = 20) -> List[Dict]:
        return [
            {"droneId": a.drone_id, "metric": a.metric,
             "value": round(a.value, 2),
             "mean":  round(a.mean,  2),
             "stdev": round(a.stdev, 2),
             "zScore": round(a.z_score, 2),
             "detectedAt": a.detected_at}
            for a in reversed(self._anomalies[-n:])
        ]
