# planning/traj_planner.py
import math
from typing import Any, List, Optional, Sequence, Tuple

from simulator.config import LANE_WIDTH

from .config import (
    CRUISE_SPEED,
    MIN_SPEED,
    STOP_DISTANCE,
    SLOW_DISTANCE,
    OBSTACLE_LATERAL_CLEARANCE,
    END_SLOW_DISTANCE,
    TIME_GAP,
    MIN_GAP,
    FOLLOW_KP,
    CUTIN_LOOKAHEAD_USE_PRED,
    EGO_FRONT_LENGTH,
    DEFAULT_LEAD_HALF_LENGTH,
)


class TrajPlanner:
    """
    纵向规划：地图限速为基准，叠加 ACC 跟车（含 cut-in/cut-out）。

    - 本车道有前车 → 时距跟车：v = min(v_base, v_lead + kp*(d - d_des))
    - 邻道目标预测轨切入本车道 → 提前按前车处理（cut-in 减速）
    - 前车切出本车道 → 无 lead，回升到 v_base（cut-out 加速）
    - d_gap 为保险杠净空（后轴弧长 + 车头 − 前车半长）
    """

    def __init__(
        self,
        cruise_speed: float = CRUISE_SPEED,
        min_speed: float = MIN_SPEED,
        stop_distance: float = STOP_DISTANCE,
        slow_distance: float = SLOW_DISTANCE,
        lateral_clearance: float = OBSTACLE_LATERAL_CLEARANCE,
        end_slow_distance: float = END_SLOW_DISTANCE,
        time_gap: float = TIME_GAP,
        min_gap: float = MIN_GAP,
        follow_kp: float = FOLLOW_KP,
        cutin_use_pred: bool = CUTIN_LOOKAHEAD_USE_PRED,
        ego_front: float = EGO_FRONT_LENGTH,
        default_lead_half: float = DEFAULT_LEAD_HALF_LENGTH,
    ):
        self.cruise_speed = cruise_speed
        self.min_speed = min_speed
        self.stop_distance = stop_distance
        self.slow_distance = slow_distance
        self.lateral_clearance = lateral_clearance
        self.end_slow_distance = end_slow_distance
        self.time_gap = time_gap
        self.min_gap = min_gap
        self.follow_kp = follow_kp
        self.cutin_use_pred = cutin_use_pred
        self.ego_front = float(ego_front)
        self.default_lead_half = float(default_lead_half)
        self.last_lead: Optional[dict] = None

    def plan(
        self,
        vehicle_state: dict,
        path: List[Tuple[float, float]],
        obstacles: Sequence[Any] = (),
        predictions: Sequence[Any] = (),
        speed_limit: Optional[float] = None,
        leads: Sequence[Any] = (),
    ) -> float:
        self.last_lead = None
        if len(path) < 2:
            return 0.0

        x = float(vehicle_state["x"])
        y = float(vehicle_state["y"])
        v_ego = float(vehicle_state.get("speed", 0.0) or 0.0)

        ego_s, _, _, _ = self._project_to_path(x, y, path)
        s_remain = self._remaining_from_s(path, ego_s, x, y)
        v_base = self.cruise_speed if speed_limit is None else max(0.0, float(speed_limit))

        lead = self._select_lead(x, y, path, ego_s, obstacles, predictions, leads=leads)
        if lead is not None:
            d_gap, v_lead, source = lead
            v_acc = self._acc_target_speed(v_ego, d_gap, v_lead, v_base)
            self.last_lead = {
                "d_gap": d_gap,
                "v_lead": v_lead,
                "source": source,
                "v_acc": v_acc,
            }
            v = v_acc
        else:
            v = v_base

        v = min(v, self._speed_from_remaining(s_remain, v_base))
        return max(0.0, v)

    def _acc_target_speed(
        self,
        v_ego: float,
        d_gap: float,
        v_lead: float,
        v_base: float,
    ) -> float:
        if d_gap <= self.stop_distance:
            return 0.0

        d_des = self.min_gap + self.time_gap * max(0.0, v_ego)
        v_cmd = v_lead + self.follow_kp * (d_gap - d_des)

        if v_lead < 0.5 and d_gap < self.slow_distance:
            v_cmd = min(v_cmd, self._speed_from_obstacle(d_gap, v_base))

        return max(0.0, min(v_base, v_cmd))

    def _select_lead(
        self,
        x: float,
        y: float,
        path: List[Tuple[float, float]],
        ego_s: float,
        obstacles: Sequence[Any],
        predictions: Sequence[Any],
        leads: Sequence[Any] = (),
    ) -> Optional[Tuple[float, float, str]]:
        best_d = float("inf")
        best: Optional[Tuple[float, float, str]] = None

        has_leads = bool(leads)
        for lead in leads:
            ox, oy, vx, vy, half = self._parse_object(lead)
            if ox is None or oy is None:
                continue
            threat = self._moving_object_threat(
                x, y, path, ego_s, ox, oy, vx, vy, half, traj=()
            )
            if threat is None:
                continue
            d_gap, v_lead, src = threat
            tag = "lead" if src == "follow" else src
            if d_gap < best_d:
                best_d = d_gap
                best = (d_gap, v_lead, tag)

        if has_leads:
            return best

        for pred in predictions:
            if getattr(pred, "coasting", False):
                continue
            ox, oy, vx, vy, half = self._parse_object(pred)
            if ox is None or oy is None:
                continue
            traj = getattr(pred, "trajectory", None) or ()
            threat = self._moving_object_threat(
                x, y, path, ego_s, ox, oy, vx, vy, half, traj=traj
            )
            if threat is None:
                continue
            d_gap, v_lead, src = threat
            if d_gap < best_d:
                best_d = d_gap
                best = (d_gap, v_lead, src)

        if best is not None:
            return best

        for obs in obstacles:
            ox, oy, _, _, half = self._parse_object(obs)
            if ox is None or oy is None:
                continue
            d_gap = self._in_lane_front_gap(x, y, path, ego_s, ox, oy, half)
            if d_gap is None:
                continue
            if d_gap < best_d:
                best_d = d_gap
                best = (d_gap, 0.0, "obstacle")

        return best

    def _parse_object(
        self, obj: Any
    ) -> Tuple[Optional[float], Optional[float], float, float, float]:
        if isinstance(obj, dict):
            ox = obj.get("x")
            oy = obj.get("y")
            vx = float(obj.get("vx", 0.0) or 0.0)
            vy = float(obj.get("vy", 0.0) or 0.0)
            w = float(obj.get("width", 0.0) or 0.0)
            h = float(obj.get("height", 0.0) or 0.0)
        else:
            ox = getattr(obj, "x", None)
            oy = getattr(obj, "y", None)
            vx = float(getattr(obj, "vx", 0.0) or 0.0)
            vy = float(getattr(obj, "vy", 0.0) or 0.0)
            w = float(getattr(obj, "width", 0.0) or 0.0)
            h = float(getattr(obj, "height", 0.0) or 0.0)
        if ox is None or oy is None:
            return None, None, 0.0, 0.0, self.default_lead_half
        half = 0.5 * max(w, h, 0.0)
        if half < 1e-6:
            half = self.default_lead_half
        return float(ox), float(oy), vx, vy, half

    def _moving_object_threat(
        self,
        x: float,
        y: float,
        path: List[Tuple[float, float]],
        ego_s: float,
        ox: float,
        oy: float,
        vx: float,
        vy: float,
        half: float,
        traj: Sequence[Any] = (),
    ) -> Optional[Tuple[float, float, str]]:
        d_now = self._in_lane_front_gap(x, y, path, ego_s, ox, oy, half)
        if d_now is not None:
            v_lead = self._speed_along_path(path, ox, oy, vx, vy)
            return d_now, max(0.0, v_lead), "follow"

        if not self.cutin_use_pred:
            return None

        _, lat, _, _ = self._project_to_path(ox, oy, path)
        alat = abs(lat)
        if alat <= self.lateral_clearance:
            return None
        if alat > self.lateral_clearance + LANE_WIDTH:
            return None
        _, lat1, _, _ = self._project_to_path(ox + vx * 1.0, oy + vy * 1.0, path)
        if abs(lat1) >= alat - 0.15:
            return None

        best_d: Optional[float] = None
        future_pts: List[Tuple[float, float]] = []
        if traj and len(traj) >= 2:
            for pt in traj[1:]:
                if pt and len(pt) >= 2:
                    future_pts.append((float(pt[0]), float(pt[1])))
        else:
            for k in (1.0, 1.5, 2.0):
                future_pts.append((ox + vx * k, oy + vy * k))

        for fx, fy in future_pts:
            d = self._in_lane_front_gap(x, y, path, ego_s, fx, fy, half)
            if d is None:
                continue
            if best_d is None or d < best_d:
                best_d = d
        if best_d is None:
            return None
        v_lead = self._speed_along_path(path, ox, oy, vx, vy)
        return best_d, max(0.0, v_lead), "cutin"

    def _in_lane_front_gap(
        self,
        x: float,
        y: float,
        path: List[Tuple[float, float]],
        ego_s: float,
        ox: float,
        oy: float,
        lead_half: float,
    ) -> Optional[float]:
        """本车道前方目标的保险杠净空；否则 None。"""
        obs_s, lat, _, _ = self._project_to_path(ox, oy, path)
        if abs(lat) > self.lateral_clearance:
            return None
        d_center = obs_s - ego_s
        if d_center <= 1e-6:
            return None  # 中心不在前方
        # 保险杠净空；已重叠时为 0 → 触发刹停
        return max(0.0, d_center - lead_half - self.ego_front)

    def _project_to_path(
        self,
        x: float,
        y: float,
        path: List[Tuple[float, float]],
    ) -> Tuple[float, float, int, float]:
        """
        投影到折线最近点。
        :return: (弧长 s, 左侧为正的横向距, 段索引, 段内 t)
        """
        best_d2 = float("inf")
        best_s = 0.0
        best_lat = 0.0
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
            d2 = (x - px) ** 2 + (y - py) ** 2
            if d2 < best_d2:
                best_d2 = d2
                tx, ty = dx / L, dy / L
                # 左侧法向
                best_lat = -ty * (x - px) + tx * (y - py)
                best_s = s_acc + t * L
                best_i = i
                best_t = t
            s_acc += L

        return best_s, best_lat, best_i, best_t

    def _speed_along_path(
        self,
        path: List[Tuple[float, float]],
        ox: float,
        oy: float,
        vx: float,
        vy: float,
    ) -> float:
        _, _, seg_i, _ = self._project_to_path(ox, oy, path)
        i = min(seg_i, len(path) - 2)
        dx = path[i + 1][0] - path[i][0]
        dy = path[i + 1][1] - path[i][1]
        L = math.hypot(dx, dy)
        if L < 1e-9:
            return math.hypot(vx, vy)
        tx, ty = dx / L, dy / L
        return vx * tx + vy * ty

    def _closest_index(
        self,
        x: float,
        y: float,
        path: List[Tuple[float, float]],
    ) -> int:
        """兼容旧调用；优先返回投影段终点索引。"""
        _, _, seg_i, t = self._project_to_path(x, y, path)
        if t > 0.5 and seg_i + 1 < len(path):
            return seg_i + 1
        return seg_i

    def _remaining_from_s(
        self,
        path: List[Tuple[float, float]],
        s: float,
        x: float,
        y: float,
    ) -> float:
        total = 0.0
        for i in range(len(path) - 1):
            total += math.hypot(path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1])
        if s >= total - 1e-6:
            if len(path) >= 2:
                x0, y0 = path[-2]
                x1, y1 = path[-1]
                if (x - x1) * (x1 - x0) + (y - y1) * (y1 - y0) > 0:
                    return 0.0
            return 0.0
        return max(0.0, total - s)

    def _remaining_arclength(
        self,
        path: List[Tuple[float, float]],
        closest_idx: int,
        x: float,
        y: float,
    ) -> float:
        s, _, _, _ = self._project_to_path(x, y, path)
        return self._remaining_from_s(path, s, x, y)

    def _path_arclength_between(
        self,
        path: List[Tuple[float, float]],
        start_idx: int,
        end_idx: int,
        x: float,
        y: float,
    ) -> float:
        """兼容旧测试：用投影弧长差近似。"""
        s0, _, _, _ = self._project_to_path(x, y, path)
        if end_idx < 0 or end_idx >= len(path):
            return float("inf")
        s1, _, _, _ = self._project_to_path(path[end_idx][0], path[end_idx][1], path)
        return max(0.0, s1 - s0)

    def _speed_from_obstacle(self, d_obs: float, v_base: float) -> float:
        if d_obs >= self.slow_distance:
            return v_base
        if d_obs <= self.stop_distance:
            return 0.0
        ratio = (d_obs - self.stop_distance) / (self.slow_distance - self.stop_distance)
        v_lo = min(self.min_speed, v_base)
        return v_lo + ratio * (v_base - v_lo)

    def _speed_from_remaining(self, s_remain: float, v_base: float) -> float:
        if s_remain >= self.end_slow_distance:
            return v_base
        if s_remain <= 0.0:
            return 0.0
        return v_base * (s_remain / self.end_slow_distance)
