# control/pure_pursuit.py
import math
from typing import List, Optional, Tuple

from config import DT
from simulator.config import WHEEL_BASE, MAX_STEER_ANGLE, MAX_ACC, MAX_DECEL

from .config import (
    LOOKAHEAD_DISTANCE,
    LOOKAHEAD_GAIN,
    LOOKAHEAD_MAX,
    LOOKAHEAD_MIN,
    MAX_STEER_RATE,
    TARGET_SPEED,
    SPEED_KP,
)


class PurePursuit:
    """
    Pure Pursuit 横向跟踪 + 纵向速度 P 控制。

    预瞄点沿路径弧长插值（非离散跳点），Ld 随车速变化，并对转角限速，
    减轻直线上的画龙振荡。
    """

    def __init__(
        self,
        lookahead: float = LOOKAHEAD_DISTANCE,
        target_speed: float = TARGET_SPEED,
        speed_kp: float = SPEED_KP,
        wheel_base: float = WHEEL_BASE,
        lookahead_gain: float = LOOKAHEAD_GAIN,
        lookahead_min: float = LOOKAHEAD_MIN,
        lookahead_max: float = LOOKAHEAD_MAX,
        max_steer_rate: float = MAX_STEER_RATE,
    ):
        self.lookahead = lookahead  # 兼容：无速度时的回退
        self.lookahead_gain = lookahead_gain
        self.lookahead_min = lookahead_min
        self.lookahead_max = lookahead_max
        self.target_speed = target_speed
        self.speed_kp = speed_kp
        self.wheel_base = wheel_base
        self.max_steer_rate = max_steer_rate
        self._prev_steer = 0.0

    def reset(self) -> None:
        self._prev_steer = 0.0

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

        x = float(vehicle_state["x"])
        y = float(vehicle_state["y"])
        yaw = float(vehicle_state["yaw"])
        speed = float(vehicle_state["speed"])

        v_target = self.target_speed if target_speed is None else target_speed
        ld = self._lookahead_distance(speed)

        target = self._find_lookahead_point(x, y, path, ld)
        steer = self._calc_steer(x, y, yaw, target)
        steer = self._rate_limit_steer(steer)
        acc = self._calc_acc(speed, v_target)

        acc = max(MAX_DECEL, min(MAX_ACC, acc))
        steer = max(-MAX_STEER_ANGLE, min(MAX_STEER_ANGLE, steer))
        self._prev_steer = steer
        return acc, steer

    def get_lookahead_point(
        self,
        vehicle_state: dict,
        path: List[Tuple[float, float]],
    ) -> Optional[Tuple[float, float]]:
        """供可视化等模块查询当前预瞄点；空路径返回 None。"""
        if not path:
            return None
        speed = float(vehicle_state.get("speed", 0.0) or 0.0)
        ld = self._lookahead_distance(speed)
        return self._find_lookahead_point(
            float(vehicle_state["x"]), float(vehicle_state["y"]), path, ld
        )

    def get_preview_trajectory(
        self,
        vehicle_state: dict,
        path: List[Tuple[float, float]],
        n_path: int = 14,
        n_arc: int = 18,
    ) -> dict:
        """
        可视化用预瞄轨迹：
        - path_preview: 自车投影点沿参考路径到预瞄点
        - arc_preview: Pure Pursuit 几何圆弧（当前位姿 → 预瞄点）
        """
        empty = {"path_preview": [], "arc_preview": [], "lookahead": None, "ld": 0.0}
        if not path:
            return empty
        x = float(vehicle_state["x"])
        y = float(vehicle_state["y"])
        yaw = float(vehicle_state.get("yaw", 0.0) or 0.0)
        speed = float(vehicle_state.get("speed", 0.0) or 0.0)
        ld = self._lookahead_distance(speed)
        target = self._find_lookahead_point(x, y, path, ld)
        path_preview = self._sample_path_to_lookahead(x, y, path, ld, n_path)
        arc_preview = self._sample_pp_arc(x, y, yaw, target, n_arc)
        return {
            "path_preview": path_preview,
            "arc_preview": arc_preview,
            "lookahead": [float(target[0]), float(target[1])],
            "ld": float(ld),
        }

    def _sample_path_to_lookahead(
        self,
        x: float,
        y: float,
        path: List[Tuple[float, float]],
        ld: float,
        n: int,
    ) -> List[List[float]]:
        if len(path) < 2 or n < 2:
            return []
        _, s0, seg_i, t0 = self._project_on_path(x, y, path)
        target_s = s0 + max(ld, 0.0)
        # 总弧长上限
        total = 0.0
        for i in range(len(path) - 1):
            total += self._seg_len(path, i)
        target_s = min(target_s, total)
        out: List[List[float]] = []
        for k in range(n):
            s = s0 + (target_s - s0) * (k / (n - 1))
            out.append(list(self._point_at_arclength(path, s)))
        return out

    def _point_at_arclength(
        self, path: List[Tuple[float, float]], s: float
    ) -> Tuple[float, float]:
        if s <= 0.0:
            return float(path[0][0]), float(path[0][1])
        cursor = 0.0
        for i in range(len(path) - 1):
            seg = self._seg_len(path, i)
            if cursor + seg >= s - 1e-9:
                u = 0.0 if seg < 1e-12 else (s - cursor) / seg
                u = max(0.0, min(1.0, u))
                x0, y0 = path[i]
                x1, y1 = path[i + 1]
                return float(x0 + u * (x1 - x0)), float(y0 + u * (y1 - y0))
            cursor += seg
        return float(path[-1][0]), float(path[-1][1])

    def _sample_pp_arc(
        self,
        x: float,
        y: float,
        yaw: float,
        target: Tuple[float, float],
        n: int,
    ) -> List[List[float]]:
        """按 PP 曲率画一段圆弧（车体 +x 前、+y 左）。"""
        if n < 2:
            return []
        tx, ty = float(target[0]), float(target[1])
        dx, dy = tx - x, ty - y
        c, s = math.cos(yaw), math.sin(yaw)
        x_r = c * dx + s * dy
        y_r = -s * dx + c * dy
        ld = math.hypot(x_r, y_r)
        if ld < 1e-6 or x_r < 0.0:
            return [[x, y], [tx, ty]]

        alpha = math.atan2(y_r, x_r)
        sin_a = math.sin(alpha)
        if abs(sin_a) < 1e-6:
            return [
                [x + (tx - x) * k / (n - 1), y + (ty - y) * k / (n - 1)]
                for k in range(n)
            ]

        # kappa = 2 sin(α)/Ld；圆心角 ≈ 2α
        R = ld / (2.0 * sin_a)
        dphi = 2.0 * alpha
        out: List[List[float]] = []
        for k in range(n):
            phi = dphi * (k / (n - 1))
            bx = R * math.sin(phi)
            by = R * (1.0 - math.cos(phi))
            wx = x + c * bx - s * by
            wy = y + s * bx + c * by
            out.append([float(wx), float(wy)])
        out[-1] = [tx, ty]
        return out

    def _lookahead_distance(self, speed: float) -> float:
        ld = self.lookahead_gain * max(float(speed), 1.0)
        return max(self.lookahead_min, min(self.lookahead_max, ld))

    def _rate_limit_steer(self, steer: float) -> float:
        if self.max_steer_rate <= 0.0 or DT <= 0.0:
            return steer
        max_step = self.max_steer_rate * DT
        lo = self._prev_steer - max_step
        hi = self._prev_steer + max_step
        return max(lo, min(hi, steer))

    def _find_lookahead_point(
        self,
        x: float,
        y: float,
        path: List[Tuple[float, float]],
        ld: float,
    ) -> Tuple[float, float]:
        """
        投影到路径折线后，沿弧长前进 ld，段内线性插值预瞄点。
        """
        if len(path) == 1:
            return float(path[0][0]), float(path[0][1])

        _, s0, seg_i, t0 = self._project_on_path(x, y, path)
        target_s = s0 + max(ld, 0.0)

        # 从投影段起向前累积弧长
        s_at_seg_start = s0 - t0 * self._seg_len(path, seg_i)
        s_cursor = s_at_seg_start
        for i in range(seg_i, len(path) - 1):
            seg_len = self._seg_len(path, i)
            if seg_len < 1e-12:
                continue
            if s_cursor + seg_len >= target_s - 1e-9:
                u = (target_s - s_cursor) / seg_len
                u = max(0.0, min(1.0, u))
                x0, y0 = path[i]
                x1, y1 = path[i + 1]
                return float(x0 + u * (x1 - x0)), float(y0 + u * (y1 - y0))
            s_cursor += seg_len
        return float(path[-1][0]), float(path[-1][1])

    @staticmethod
    def _seg_len(path: List[Tuple[float, float]], i: int) -> float:
        x0, y0 = path[i]
        x1, y1 = path[i + 1]
        return math.hypot(x1 - x0, y1 - y0)

    def _project_on_path(
        self,
        x: float,
        y: float,
        path: List[Tuple[float, float]],
    ) -> Tuple[Tuple[float, float], float, int, float]:
        """
        :return: (投影点, 自起点弧长, 段索引, 段内比例 t∈[0,1])
        """
        best_d = float("inf")
        best_pt = (float(path[0][0]), float(path[0][1]))
        best_s = 0.0
        best_i = 0
        best_t = 0.0
        s_acc = 0.0

        for i in range(len(path) - 1):
            x0, y0 = float(path[i][0]), float(path[i][1])
            x1, y1 = float(path[i + 1][0]), float(path[i + 1][1])
            dx, dy = x1 - x0, y1 - y0
            L = math.hypot(dx, dy)
            if L < 1e-12:
                continue
            t = ((x - x0) * dx + (y - y0) * dy) / (L * L)
            t = max(0.0, min(1.0, t))
            px, py = x0 + t * dx, y0 + t * dy
            d = math.hypot(x - px, y - py)
            if d < best_d:
                best_d = d
                best_pt = (px, py)
                best_s = s_acc + t * L
                best_i = i
                best_t = t
            s_acc += L

        return best_pt, best_s, best_i, best_t

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

        cos_yaw = math.cos(yaw)
        sin_yaw = math.sin(yaw)
        x_r = cos_yaw * dx + sin_yaw * dy
        y_r = -sin_yaw * dx + cos_yaw * dy

        ld = math.hypot(x_r, y_r)
        if ld < 1e-6:
            return 0.0
        # 目标在车体后方时不猛打方向（避免画龙）
        if x_r < 0.0:
            return 0.0

        alpha = math.atan2(y_r, x_r)
        return math.atan2(2.0 * self.wheel_base * math.sin(alpha), ld)

    def _calc_acc(self, speed: float, target_speed: float) -> float:
        """纵向：acc = kp * (v_target - v)"""
        return self.speed_kp * (target_speed - speed)
