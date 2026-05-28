from __future__ import annotations
import numpy as np
from dataclasses import dataclass, field
from typing      import Dict, List, Optional

from .kalman_filter import ExtendedKalmanFilter

# ── Base weights (sum to 1.0) ──────────────────────────
W_GPS   = 0.45
W_IMU   = 0.15
W_SLAM  = 0.25
W_LIDAR = 0.15

# Thresholds for dynamic weight adjustment
GPS_SIG_OK    = 40    # % signal for full GPS weight
SLAM_CONF_OK  = 0.6  # SLAM confidence for full weight

@dataclass
class SensorReadings:
    # GPS
    gps_pos:    np.ndarray          # [lat_m, lon_m, alt_m]
    gps_signal: float               # 0–100 %
    # IMU
    imu_acc:    np.ndarray          # [ax, ay, az] m/s²
    imu_gyro:   np.ndarray          # [gx, gy, gz] rad/s
    # Visual SLAM
    slam_pos:   Optional[np.ndarray]  # [x, y, z] or None if lost
    slam_conf:  float = 0.0
    # LiDAR terrain estimate
    lidar_z:    Optional[float] = None   # ground clearance m

@dataclass
class FusedPosition:
    x:        float
    y:        float
    z:        float
    vx:       float = 0.0
    vy:       float = 0.0
    vz:       float = 0.0
    quality:  float = 1.0   # 0–1 overall confidence
    sources:  List[str] = field(default_factory=list)

class EdgeSensorFusion:
    """
    Edge-side 4-sensor fusion pipeline.
    Runs on drone compute; much tighter loop than backend fusion.

    Pipeline per tick:
      1. Compute dynamic weights from source quality
      2. Build blended measurement vector
      3. Feed into EKF predict + update
      4. Return FusedPosition with quality score
    """

    def __init__(self, drone_id: str):
        self.drone_id = drone_id
        self._ekf     = ExtendedKalmanFilter(state_dim=6)
        self._tick    = 0

    # ── Main fusion tick ──────────────────────────────────
    def fuse(self, readings: SensorReadings, dt: float = 0.1) -> FusedPosition:
        """Fuse all available sensor readings into one position estimate."""
        self._tick += 1
        weights, sources = self._compute_weights(readings)
        blended          = self._blend(readings, weights)

        # EKF predict step (motion model)
        self._ekf.predict(dt)

        # EKF update step (blended measurement)
        state = self._ekf.update(blended)

        quality = self._quality_score(weights, readings)

        return FusedPosition(
            x=float(state[0]),
            y=float(state[1]),
            z=float(state[2]),
            vx=float(state[3]),
            vy=float(state[4]),
            vz=float(state[5]),
            quality=quality,
            sources=sources,
        )

    # ── Dynamic weight computation ────────────────────────
    def _compute_weights(
        self, r: SensorReadings
    ) -> tuple[Dict[str, float], List[str]]:
        """
        Adjust base weights by source health.
        GPS weight drops linearly below GPS_SIG_OK.
        SLAM weight drops to 0 when lost (slam_pos is None).
        LiDAR weight drops to 0 when no Z reading available.
        Remaining budget redistributed proportionally.
        """
        w = {
            "gps":   W_GPS   * min(1.0, r.gps_signal / GPS_SIG_OK),
            "imu":   W_IMU,
            "slam":  W_SLAM  * (r.slam_conf / SLAM_CONF_OK
                         if r.slam_pos is not None else 0.0),
            "lidar": W_LIDAR * (1.0 if r.lidar_z is not None else 0.0),
        }
        total   = sum(w.values()) or 1e-8
        w       = {k: v / total for k, v in w.items()}   # renormalise
        sources = [k for k, v in w.items() if v > 0.05]
        return w, sources

    # ── Weighted measurement blend ────────────────────────
    def _blend(self, r: SensorReadings, w: Dict) -> np.ndarray:
        """Build a 3-element [x, y, z] blended measurement."""
        gps  = r.gps_pos
        imu  = np.array([r.imu_acc[0], r.imu_acc[1], 0.0])
        slam = r.slam_pos if r.slam_pos is not None else gps
        lidar_z = r.lidar_z if r.lidar_z is not None else gps[2]
        lidar = np.array([gps[0], gps[1], lidar_z])

        return (
            w["gps"]   * gps
            + w["imu"]   * imu
            + w["slam"]  * slam
            + w["lidar"] * lidar
        )

    # ── Overall quality score ─────────────────────────────
    def _quality_score(self, w: Dict, r: SensorReadings) -> float:
        """
        Weighted confidence score: GPS and SLAM dominate.
        Degrades gracefully as sources drop out.
        """
        gps_q  = min(1.0, r.gps_signal / 100)
        slam_q = r.slam_conf if r.slam_pos is not None else 0.0
        return float(
            w["gps"] * gps_q + w["slam"] * slam_q
            + w["imu"] * 0.8 + w["lidar"] * 0.9
        )
