# simulator/world.py
from __future__ import annotations

from typing import List, Sequence, Tuple

from .config import (
    FRONT_OVERHANG,
    LANE_WIDTH,
    REAR_OVERHANG,
    VEHICLE_LENGTH,
    VEHICLE_WIDTH,
    WHEEL_BASE,
)
from .geometry import lane_boundaries
from .vehicle import Vehicle


class Obstacle:
    """静态矩形障碍物"""

    def __init__(self, x: float, y: float, width: float, height: float):
        self.x = x
        self.y = y
        self.width = width
        self.height = height


class SimulationWorld:
    def __init__(self):
        self.vehicle = Vehicle()
        self.obstacles = []
        # 参考路径 = 车道中心线；自车后轴中心应沿此线行驶
        self.reference_path: List[Tuple[float, float]] = []
        self.lane_width = LANE_WIDTH

    def reset(self) -> None:
        """重置仿真世界：车辆归位，保留障碍物与路径配置"""
        self.vehicle.reset()

    def add_obstacle(self, x: float, y: float, width: float, height: float) -> None:
        self.obstacles.append(Obstacle(x, y, width, height))

    def set_reference_path(self, path: list) -> None:
        """
        设置车道中心线（参考路径）。
        :param path: [(x, y), ...]
        """
        self.reference_path = [(float(p[0]), float(p[1])) for p in path]

    def get_lane_boundaries(self, path: Sequence[Tuple[float, float]] | None = None) -> dict:
        """中心线 + 左右边界（宽度 LANE_WIDTH）。"""
        center = path if path is not None else self.reference_path
        return lane_boundaries(center, self.lane_width)

    def get_vehicle_geom(self) -> dict:
        """自车外形与参考点说明（后轴中心）。"""
        return {
            "width": VEHICLE_WIDTH,
            "length": VEHICLE_LENGTH,
            "wheel_base": WHEEL_BASE,
            "rear_overhang": REAR_OVERHANG,
            "front_overhang": FRONT_OVERHANG,
            "ref_point": "rear_axle",
            "lane_width": self.lane_width,
        }

    def step(self, acceleration: float, steer_angle: float) -> None:
        self.vehicle.step(acceleration, steer_angle)

    def get_state(self) -> dict:
        return {
            "vehicle": self.vehicle.get_state(),
            "obstacle_count": len(self.obstacles),
            "path_point_num": len(self.reference_path),
            "lane_width": self.lane_width,
            "vehicle_geom": self.get_vehicle_geom(),
        }
