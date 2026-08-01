# planning/traj_planner.py
import math
from typing import List, Optional, Sequence, Tuple, Any

from .config import (
    CRUISE_SPEED,
    MIN_SPEED,
    STOP_DISTANCE,
    SLOW_DISTANCE,
    OBSTACLE_LATERAL_CLEARANCE,
    END_SLOW_DISTANCE,
)


class TrajPlanner:
    """
    纵向轨迹规划（教学简化版）：沿密化路径估计剩余弧长与前方障碍距离，
    输出瞬时 target_speed，对接 PurePursuit.compute(..., target_speed=...).
    """

    def __init__(
        self,
        cruise_speed: float = CRUISE_SPEED,
        min_speed: float = MIN_SPEED,
        stop_distance: float = STOP_DISTANCE,
        slow_distance: float = SLOW_DISTANCE,
        lateral_clearance: float = OBSTACLE_LATERAL_CLEARANCE,
        end_slow_distance: float = END_SLOW_DISTANCE,
    ):
        self.cruise_speed = cruise_speed
        self.min_speed = min_speed
        self.stop_distance = stop_distance
        self.slow_distance = slow_distance
        self.lateral_clearance = lateral_clearance
        self.end_slow_distance = end_slow_distance

    def plan(
        self,
        vehicle_state: dict,
        path: List[Tuple[float, float]],
        obstacles: Sequence[Any] = (),
        predictions: Sequence[Any] = (),
        speed_limit: Optional[float] = None,
    ) -> float:
        """
        :param predictions: PredictedObstacle 列表（可选）；用其 trajectory 点做前瞻挡路减速
        :param speed_limit: 地图限速基准（m/s）；None 时用 cruise_speed
        :return: 目标车速 m/s（非负）
        """
        if len(path) < 2:
            return 0.0

        x = vehicle_state["x"]
        y = vehicle_state["y"]

        closest_idx = self._closest_index(x, y, path)
        s_remain = self._remaining_arclength(path, closest_idx, x, y)
        d_obs = self._nearest_front_obstacle_distance(
            x, y, path, closest_idx, obstacles
        )
        d_pred = self._nearest_front_prediction_distance(
            x, y, path, closest_idx, predictions
        )
        d_threat = min(d_obs, d_pred)

        v_base = self.cruise_speed if speed_limit is None else max(0.0, float(speed_limit))
        v = v_base
        v = min(v, self._speed_from_obstacle(d_threat, v_base))
        v = min(v, self._speed_from_remaining(s_remain, v_base))
        return max(0.0, v)

    def _closest_index(
        self,
        x: float,
        y: float,
        path: List[Tuple[float, float]],
    ) -> int:
        return min(
            range(len(path)),
            key=lambda i: math.hypot(path[i][0] - x, path[i][1] - y),
        )

    def _remaining_arclength(
        self,
        path: List[Tuple[float, float]],
        closest_idx: int,
        x: float,
        y: float,
    ) -> float:
        """从车辆到路径最近点，再沿折线到终点的弧长；已越过终点则返回 0。"""
        if closest_idx >= len(path) - 1:
            if len(path) >= 2:
                x0, y0 = path[-2]
                x1, y1 = path[-1]
                # (车 - 终点) · (终点 - 前一点) > 0 表示已驶过终点
                if (x - x1) * (x1 - x0) + (y - y1) * (y1 - y0) > 0:
                    return 0.0
            return math.hypot(path[-1][0] - x, path[-1][1] - y)

        s = math.hypot(path[closest_idx][0] - x, path[closest_idx][1] - y)
        for i in range(closest_idx, len(path) - 1):
            x0, y0 = path[i]
            x1, y1 = path[i + 1]
            s += math.hypot(x1 - x0, y1 - y0)
        return s

    def _path_arclength_between(
        self,
        path: List[Tuple[float, float]],
        start_idx: int,
        end_idx: int,
        x: float,
        y: float,
    ) -> float:
        """车辆 → start_idx 再沿路径到 end_idx 的弧长。"""
        if end_idx < start_idx:
            return float("inf")
        s = math.hypot(path[start_idx][0] - x, path[start_idx][1] - y)
        for i in range(start_idx, end_idx):
            x0, y0 = path[i]
            x1, y1 = path[i + 1]
            s += math.hypot(x1 - x0, y1 - y0)
        return s

    def _nearest_front_obstacle_distance(
        self,
        x: float,
        y: float,
        path: List[Tuple[float, float]],
        closest_idx: int,
        obstacles: Sequence[Any],
    ) -> float:
        """
        返回路径前方最近「挡路」障碍的纵向距离；
        无障碍时返回 +inf。
        """
        if not obstacles:
            return float("inf")

        best = float("inf")
        for obs in obstacles:
            ox = getattr(obs, "x", None)
            oy = getattr(obs, "y", None)
            if ox is None or oy is None:
                continue

            obs_idx = self._closest_index(ox, oy, path)
            px, py = path[obs_idx]
            lat = math.hypot(ox - px, oy - py)
            if lat > self.lateral_clearance:
                continue
            if obs_idx < closest_idx:
                continue

            d_lon = self._path_arclength_between(path, closest_idx, obs_idx, x, y)
            if d_lon < best:
                best = d_lon

        return best

    def _nearest_front_prediction_distance(
        self,
        x: float,
        y: float,
        path: List[Tuple[float, float]],
        closest_idx: int,
        predictions: Sequence[Any],
    ) -> float:
        """
        扫描预测轨迹点，返回前方最近挡路点的纵向距离；无则 +inf。
        """
        if not predictions:
            return float("inf")

        best = float("inf")
        for pred in predictions:
            # 忽略 coasting / 仅当前位置的静止轨（无外推）
            if getattr(pred, "coasting", False):
                continue
            traj = getattr(pred, "trajectory", None) or ()
            if len(traj) < 2:
                continue
            # 当前位置已由 obstacles 覆盖；只看未来外推点做前瞻
            for pt in traj[1:]:
                if not pt or len(pt) < 2:
                    continue
                ox, oy = float(pt[0]), float(pt[1])
                obs_idx = self._closest_index(ox, oy, path)
                px, py = path[obs_idx]
                lat = math.hypot(ox - px, oy - py)
                if lat > self.lateral_clearance:
                    continue
                if obs_idx < closest_idx:
                    continue
                d_lon = self._path_arclength_between(path, closest_idx, obs_idx, x, y)
                if d_lon < best:
                    best = d_lon
        return best

    def _speed_from_obstacle(self, d_obs: float, v_base: float) -> float:
        """
        d >= SLOW → v_base；
        d <= STOP → 0；
        其间从 MIN_SPEED 线性升到 v_base。
        """
        if d_obs >= self.slow_distance:
            return v_base
        if d_obs <= self.stop_distance:
            return 0.0
        ratio = (d_obs - self.stop_distance) / (self.slow_distance - self.stop_distance)
        # min_speed 不超过基准速，避免限速很低时插值反常
        v_lo = min(self.min_speed, v_base)
        return v_lo + ratio * (v_base - v_lo)

    def _speed_from_remaining(self, s_remain: float, v_base: float) -> float:
        if s_remain >= self.end_slow_distance:
            return v_base
        if s_remain <= 0.0:
            return 0.0
        return v_base * (s_remain / self.end_slow_distance)
