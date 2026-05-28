"""Edge inference package."""

from .fusion import SensorFusion, KalmanFilter
from .models import ModelRegistry
from .yolo_detector import YOLODetector
from .slam_engine import SLAMEngine
from .lidar_processor import LidarProcessor
from .gps_fallback import fallback_position
from .obstacle_avoidance import ObstacleAvoidance

__all__ = [
    "SensorFusion",
    "KalmanFilter",
    "ModelRegistry",
    "YOLODetector",
    "SLAMEngine",
    "LidarProcessor",
    "fallback_position",
    "ObstacleAvoidance",
]
