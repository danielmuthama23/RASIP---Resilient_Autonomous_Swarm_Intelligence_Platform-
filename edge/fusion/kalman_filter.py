from __future__ import annotations
import numpy as np
from typing import Optional

# ── Noise covariance defaults ──────────────────────────
Q_SCALE = 1e-4   # process noise — motion model uncertainty
R_SCALE = 1e-2   # measurement noise — sensor uncertainty
MAHAL_THRESH = 9.0  # Mahalanobis² threshold for outlier rejection

class ExtendedKalmanFilter:
    """
    6-DOF Extended Kalman Filter.
    State vector x = [px, py, pz, vx, vy, vz]

    Motion model (predict):
      px += vx * dt
      py += vy * dt
      pz += vz * dt
      velocities unchanged (constant-velocity model)

    Measurement model (update):
      z = H @ x  where H selects position rows [0:3]

    Outlier rejection:
      Mahalanobis distance² > MAHAL_THRESH → discard measurement
    """

    def __init__(self, state_dim: int = 6):
        self.n  = state_dim
        self.m  = 3   # measurement dim (x, y, z)

        # State vector: [px, py, pz, vx, vy, vz]
        self.x  = np.zeros(self.n)

        # State covariance
        self.P  = np.eye(self.n) * 1.0

        # Process noise covariance
        self.Q  = np.eye(self.n) * Q_SCALE

        # Measurement noise covariance
        self.R  = np.eye(self.m) * R_SCALE

        # Measurement matrix H: maps state → measurement
        self.H  = np.zeros((self.m, self.n))
        self.H[:3, :3] = np.eye(3)   # select px, py, pz

    # ── State transition matrix F(dt) ─────────────────────
    def _F(self, dt: float) -> np.ndarray:
        """Constant-velocity state transition matrix."""
        F = np.eye(self.n)
        F[0, 3] = dt   # px += vx * dt
        F[1, 4] = dt   # py += vy * dt
        F[2, 5] = dt   # pz += vz * dt
        return F

    # ── Predict step ──────────────────────────────────────
    def predict(self, dt: float) -> np.ndarray:
        """
        Project state and covariance forward by dt seconds.
        Returns predicted state vector.
        """
        F       = self._F(dt)
        self.x  = F @ self.x
        self.P  = F @ self.P @ F.T + self.Q
        return self.x

    # ── Update step ───────────────────────────────────────
    def update(self, z: np.ndarray) -> np.ndarray:
        """
        Incorporate measurement z = [px, py, pz].
        Applies Mahalanobis outlier rejection before update.
        Returns updated state vector.
        """
        y = z - self.H @ self.x              # innovation
        S = self.H @ self.P @ self.H.T + self.R  # innovation cov

        # Mahalanobis distance² — reject if too far from prediction
        mahal_sq = float(y.T @ np.linalg.inv(S) @ y)
        if mahal_sq > MAHAL_THRESH:
            return self.x   # outlier — skip update

        K       = self.P @ self.H.T @ np.linalg.inv(S)  # Kalman gain
        self.x  = self.x + K @ y
        I       = np.eye(self.n)
        self.P  = (I - K @ self.H) @ self.P
        return self.x

    # ── Utility ───────────────────────────────────────────
    def position(self) -> np.ndarray:
        """Return current position estimate [px, py, pz]."""
        return self.x[:3].copy()

    def velocity(self) -> np.ndarray:
        """Return current velocity estimate [vx, vy, vz]."""
        return self.x[3:].copy()

    def uncertainty(self) -> float:
        """Return trace of position covariance as scalar uncertainty."""
        return float(np.trace(self.P[:3, :3]))

    def reset(self, pos: Optional[np.ndarray] = None) -> None:
        """Re-initialise state; optionally seed with known position."""
        self.x = np.zeros(self.n)
        if pos is not None:
            self.x[:3] = pos
        self.P = np.eye(self.n) * 1.0

    def tune(self, q_scale: float = Q_SCALE,
             r_scale: float = R_SCALE) -> None:
        """Adjust process and measurement noise at runtime."""
        self.Q = np.eye(self.n) * q_scale
        self.R = np.eye(self.m) * r_scale
