import numpy as np
from dataclasses import dataclass
from typing      import Dict

W_GPS  = 0.5   # GPS weight (degraded when signal < 40%)
W_IMU  = 0.2   # IMU weight
W_SLAM = 0.3   # Visual SLAM weight

class KalmanFilter1D:
    """Scalar 1-D Kalman filter for noise reduction."""
    def __init__(self, q: float = 1e-5, r: float = 1e-2):
        self.q = q        # process noise covariance
        self.r = r        # measurement noise covariance
        self.p = 1.0     # estimation error covariance
        self.x = 0.0     # state estimate

    def update(self, z: float) -> float:
        self.p += self.q                    # predict
        k       = self.p / (self.p + self.r) # Kalman gain
        self.x += k * (z - self.x)          # update state
        self.p *= (1 - k)                   # update error
        return self.x

class SensorFusion:
    def __init__(self):
        # One KF per drone per axis (x, y, z)
        self._kf: Dict[str, list] = {}

    def fuse(self, drone) -> Dict[str, float]:
        """Return Kalman-smoothed fused position {x, y, z}."""
        did = drone.id
        if did not in self._kf:
            self._kf[did] = [KalmanFilter1D() for _ in range(3)]

        gps  = np.array([drone.x,      drone.y,      drone.altitude])
        imu  = np.array([drone.vel[0], drone.vel[1], 0.0])
        slam = np.array([drone.slam_x, drone.slam_y, drone.slam_z])

        # Degrade GPS weight when signal is weak
        w_gps  = W_GPS if drone.signal > 40 else 0.1
        w_slam = 1.0 - w_gps - W_IMU

        blended  = w_gps * gps + W_IMU * imu + w_slam * slam
        smoothed = np.array([
            kf.update(v)
            for kf, v in zip(self._kf[did], blended)
        ])
        return {"x": float(smoothed[0]),
                "y": float(smoothed[1]),
                "z": float(smoothed[2])}
