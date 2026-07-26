# perception/camera_sim.py
import math
import random
from typing import List
from simulator.world import Obstacle
from .base import DetectedObstacle
from .config import (
    CAMERA_MAX_RANGE,
    CAMERA_FOV,
    CAMERA_POS_NOISE_STD,
    CAMERA_SIZE_NOISE_STD,
    CAMERA_DETECT_PROB_NEAR,
    CAMERA_DETECT_PROB_FAR,
    CAMERA_CATEGORIES
)


class CameraSimulator:
    """摄像头障碍物检测模拟器（带类别识别）"""
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
            if distance > CAMERA_MAX_RANGE:
                continue

            # 3. 视场角过滤（摄像头FOV更广）
            angle_global = math.atan2(dy, dx)
            angle_relative = angle_global - ego_yaw
            angle_relative = (angle_relative + math.pi) % (2 * math.pi) - math.pi
            if abs(angle_relative) > CAMERA_FOV / 2:
                continue

            # 4. 距离相关的检测概率：50m以内高概率，之外线性衰减
            if distance < 50.0:
                detect_prob = CAMERA_DETECT_PROB_NEAR
            else:
                ratio = (CAMERA_MAX_RANGE - distance) / (CAMERA_MAX_RANGE - 50.0)
                detect_prob = CAMERA_DETECT_PROB_FAR + (CAMERA_DETECT_PROB_NEAR - CAMERA_DETECT_PROB_FAR) * ratio
            if random.random() > detect_prob:
                continue

            # 5. 添加高斯噪声（摄像头噪声大，测距不准）
            noisy_x = obs.x + random.gauss(0, CAMERA_POS_NOISE_STD)
            noisy_y = obs.y + random.gauss(0, CAMERA_POS_NOISE_STD)
            noisy_w = max(0.1, obs.width + random.gauss(0, CAMERA_SIZE_NOISE_STD))
            noisy_h = max(0.1, obs.height + random.gauss(0, CAMERA_SIZE_NOISE_STD))

            # 6. 随机分配类别（模拟目标分类输出）
            category = random.choice(CAMERA_CATEGORIES)

            # 7. 置信度：距离越远置信度越低
            confidence = 1.0 - (distance / CAMERA_MAX_RANGE) * 0.5
            confidence = max(0.3, min(0.95, confidence))

            self._results.append(DetectedObstacle(
                obs_id=idx,
                x=noisy_x,
                y=noisy_y,
                width=noisy_w,
                height=noisy_h,
                confidence=confidence,
                category=category,
                source="camera"
            ))