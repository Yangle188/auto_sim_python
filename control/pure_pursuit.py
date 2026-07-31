# control/pure_pursuit.py
import math
from typing import List, Tuple, Optional
from simulator.config import WHEEL_BASE, MAX_STEER_ANGLE, MAX_ACC, MAX_DECEL
from .config import LOOKAHEAD_DISTANCE, TARGET_SPEED, SPEED_KP


class PurePursuit:
    """
    Pure Pursuit 横向跟踪 + 纵向速度 P 控制。
    输出 (acceleration, steer_angle)，对接 Vehicle.step / World.step。
    """

    def __init__(
        self,
        lookahead: float = LOOKAHEAD_DISTANCE,
        target_speed: float = TARGET_SPEED,
        speed_kp: float = SPEED_KP,
        wheel_base: float = WHEEL_BASE,
    ):
        self.lookahead = lookahead
        self.target_speed = target_speed
        self.speed_kp = speed_kp
        self.wheel_base = wheel_base

    def compute(
        self,
        vehicle_state: dict,
        path: List[Tuple[float, float]],
        target_speed: Optional[float] = None,
    ) -> Tuple[float, float]:
        """
        :return: (acceleration m/s², steer_angle rad)
        """
        if not path:
            return 0.0, 0.0

        x = vehicle_state["x"]
        y = vehicle_state["y"]
        yaw = vehicle_state["yaw"]
        speed = vehicle_state["speed"]

        v_target = self.target_speed if target_speed is None else target_speed

        target = self._find_lookahead_point(x, y, path)
        steer = self._calc_steer(x, y, yaw, target)
        acc = self._calc_acc(speed, v_target)

        acc = max(MAX_DECEL, min(MAX_ACC, acc))
        steer = max(-MAX_STEER_ANGLE, min(MAX_STEER_ANGLE, steer))
        return acc, steer

    def _find_lookahead_point(
        self,
        x: float,
        y: float,
        path: List[Tuple[float, float]],
    ) -> Tuple[float, float]:
        """
        先找最近路点，再沿路径向前找第一个距离 >= lookahead 的点；
        若没有则取终点。避免选中车身后的点。
        """
        closest_idx = min(
            range(len(path)),
            key=lambda i: math.hypot(path[i][0] - x, path[i][1] - y),
        )
        for i in range(closest_idx + 1, len(path)):
            px, py = path[i]
            if math.hypot(px - x, py - y) >= self.lookahead:
                return px, py
        return path[-1]

    def _calc_steer(
        self,
        x: float,
        y: float,
        yaw: float,
        target: Tuple[float, float],
    ) -> float:
        """
        Pure Pursuit 转角：
        1) 目标点转到车体坐标 (x_r, y_r)
        2) alpha = atan2(y_r, x_r)
        3) delta = atan(2 * L * sin(alpha) / Ld)
        """
        tx, ty = target
        dx = tx - x
        dy = ty - y

        # 世界系 → 车体坐标
        cos_yaw = math.cos(yaw)
        sin_yaw = math.sin(yaw)
        x_r = cos_yaw * dx + sin_yaw * dy
        y_r = -sin_yaw * dx + cos_yaw * dy

        ld = math.hypot(x_r, y_r)
        if ld < 1e-6:
            return 0.0

        alpha = math.atan2(y_r, x_r)
        return math.atan2(2.0 * self.wheel_base * math.sin(alpha), ld)

    def _calc_acc(self, speed: float, target_speed: float) -> float:
        """纵向：acc = kp * (v_target - v)"""
        return self.speed_kp * (target_speed - speed)
