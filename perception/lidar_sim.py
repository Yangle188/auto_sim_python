# perception/lidar_sim.py
import math
import random
from typing import List
from simulator.world import Obstacle
from .base import DetectedObstacle
from .config import (
    LIDAR_MAX_RANGE,
    LIDAR_FOV,
    LIDAR_POS_NOISE_STD,
    LIDAR_SIZE_NOISE_STD,
    LIDAR_DETECT_PROB
)


class LidarSimulator:
    """激光雷达障碍物检测模拟器"""
    def __init__(self):
        self._results: List[DetectedObstacle] = []

    def reset(self) -> None:
        self._results.clear()

    def get_results(self) -> List[DetectedObstacle]:
        return self._results.copy()

    def step(self, ego_x: float, ego_y: float, ego_yaw: float, true_obstacles: List[Obstacle]) -> None:
        self._results.clear()

        for idx, obs in enumerate(true_obstacles):
            # 1. 计算相对距离与角度
            dx = obs.x - ego_x
            dy = obs.y - ego_y
            distance = math.hypot(dx, dy)

            # 2. 距离过滤
            if distance > LIDAR_MAX_RANGE:
                continue

            # 3. 视场角过滤
            angle_global = math.atan2(dy, dx)
            angle_relative = angle_global - ego_yaw
            angle_relative = (angle_relative + math.pi) % (2 * math.pi) - math.pi
            if abs(angle_relative) > LIDAR_FOV / 2:
                continue

            # 4. 检测概率模拟
            if random.random() > LIDAR_DETECT_PROB:
                continue

            # 5. 添加高斯噪声（激光雷达噪声小）
            noisy_x = obs.x + random.gauss(0, LIDAR_POS_NOISE_STD)
            noisy_y = obs.y + random.gauss(0, LIDAR_POS_NOISE_STD)
            noisy_w = max(0.1, obs.width + random.gauss(0, LIDAR_SIZE_NOISE_STD))
            noisy_h = max(0.1, obs.height + random.gauss(0, LIDAR_SIZE_NOISE_STD))

            # 6. 置信度计算：距离越近置信度越高
            confidence = 1.0 - (distance / LIDAR_MAX_RANGE) * 0.2
            confidence = max(0.6, min(1.0, confidence))

            self._results.append(DetectedObstacle(
                obs_id=idx,
                x=noisy_x,
                y=noisy_y,
                width=noisy_w,
                height=noisy_h,
                confidence=confidence,
                category="unknown",
                source="lidar"
            ))