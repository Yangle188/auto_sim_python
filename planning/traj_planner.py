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
)


class TrajPlanner:
    """
    纵向规划：地图限速为基准，叠加 ACC 跟车（含 cut-in/cut-out）。

    - 本车道有前车 → 时距跟车：v = min(v_base, v_lead + kp*(d - d_des))
    - 邻道目标预测轨切入本车道 → 提前按前车处理（cut-in 减速）
    - 前车切出本车道 → 无 lead，回升到 v_base（cut-out 加速）
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
        # 上一帧 lead 调试信息（供 HUD / 单测）
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
        """
        :param predictions: PredictedObstacle 列表；提供 vx/vy 与 cut-in 前瞻
        :param leads: 可选真值/融合前车 {x,y,vx,vy}，优先于 predictions（仿真 ACC 更稳）
        :param speed_limit: 地图限速基准（m/s）；None 时用 cruise_speed
        :return: 目标车速 m/s（非负）
        """
        self.last_lead = None
        if len(path) < 2:
            return 0.0

        x = float(vehicle_state["x"])
        y = float(vehicle_state["y"])
        v_ego = float(vehicle_state.get("speed", 0.0) or 0.0)

        closest_idx = self._closest_index(x, y, path)
        s_remain = self._remaining_arclength(path, closest_idx, x, y)
        v_base = self.cruise_speed if speed_limit is None else max(0.0, float(speed_limit))

        lead = self._select_lead(
            x, y, path, closest_idx, obstacles, predictions, leads=leads
        )
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
            # 无前车：自由巡航到限速（cut-out 后加速）
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
        """时距 ACC：过近刹停；否则匹配前车速并按间距误差修正。"""
        if d_gap <= self.stop_distance:
            return 0.0

        d_des = self.min_gap + self.time_gap * max(0.0, v_ego)
        v_cmd = v_lead + self.follow_kp * (d_gap - d_des)

        # 静态/极慢前车：叠加距离剖面，避免高速逼近静止物
        if v_lead < 0.5 and d_gap < self.slow_distance:
            v_cmd = min(v_cmd, self._speed_from_obstacle(d_gap, v_base))

        return max(0.0, min(v_base, v_cmd))

    def _select_lead(
        self,
        x: float,
        y: float,
        path: List[Tuple[float, float]],
        closest_idx: int,
        obstacles: Sequence[Any],
        predictions: Sequence[Any],
        leads: Sequence[Any] = (),
    ) -> Optional[Tuple[float, float, str]]:
        """
        选最近本车道（或即将 cut-in）前车。
        :return: (d_gap, v_lead, source) 或 None
        """
        best_d = float("inf")
        best: Optional[Tuple[float, float, str]] = None

        # 1) 显式 leads（仿真真值：动态前车 + 静态 v=0）优先
        has_leads = bool(leads)
        for lead in leads:
            if isinstance(lead, dict):
                ox = lead.get("x")
                oy = lead.get("y")
                vx = float(lead.get("vx", 0.0) or 0.0)
                vy = float(lead.get("vy", 0.0) or 0.0)
            else:
                ox = getattr(lead, "x", None)
                oy = getattr(lead, "y", None)
                vx = float(getattr(lead, "vx", 0.0) or 0.0)
                vy = float(getattr(lead, "vy", 0.0) or 0.0)
            if ox is None or oy is None:
                continue
            threat = self._moving_object_threat(
                x, y, path, closest_idx, float(ox), float(oy), vx, vy, traj=()
            )
            if threat is None:
                continue
            d_gap, v_lead, src = threat
            tag = "lead" if src == "follow" else src
            if d_gap < best_d:
                best_d = d_gap
                best = (d_gap, v_lead, tag)

        # 有 leads 时不再吃感知/预测（避免 cut-out 后噪声误跟）。
        # 静态画布障碍应由调用方一并放进 leads（v=0），见 SimSession._truth_leads。
        if has_leads:
            return best

        # 2) 预测轨
        for pred in predictions:
            if getattr(pred, "coasting", False):
                continue
            threat = self._prediction_threat(x, y, path, closest_idx, pred)
            if threat is None:
                continue
            d_gap, v_lead, src = threat
            if d_gap < best_d:
                best_d = d_gap
                best = (d_gap, v_lead, src)

        if best is not None:
            return best

        # 3) 静止/未知速度障碍兜底（无 leads 时）
        for obs in obstacles:
            ox = getattr(obs, "x", None)
            oy = getattr(obs, "y", None)
            if ox is None or oy is None:
                continue
            d_gap = self._in_lane_front_distance(
                x, y, path, closest_idx, float(ox), float(oy)
            )
            if d_gap is None:
                continue
            if d_gap < best_d:
                best_d = d_gap
                best = (d_gap, 0.0, "obstacle")

        return best

    def _prediction_threat(
        self,
        x: float,
        y: float,
        path: List[Tuple[float, float]],
        closest_idx: int,
        pred: Any,
    ) -> Optional[Tuple[float, float, str]]:
        ox = float(getattr(pred, "x"))
        oy = float(getattr(pred, "y"))
        vx = float(getattr(pred, "vx", 0.0) or 0.0)
        vy = float(getattr(pred, "vy", 0.0) or 0.0)
        traj = getattr(pred, "trajectory", None) or ()
        return self._moving_object_threat(
            x, y, path, closest_idx, ox, oy, vx, vy, traj=traj
        )

    def _moving_object_threat(
        self,
        x: float,
        y: float,
        path: List[Tuple[float, float]],
        closest_idx: int,
        ox: float,
        oy: float,
        vx: float,
        vy: float,
        traj: Sequence[Any] = (),
    ) -> Optional[Tuple[float, float, str]]:
        d_now = self._in_lane_front_distance(x, y, path, closest_idx, ox, oy)
        if d_now is not None:
            v_lead = self._speed_along_path(path, ox, oy, vx, vy)
            return d_now, max(0.0, v_lead), "follow"

        if not self.cutin_use_pred:
            return None

        # cut-in：当前在邻道且正在靠近中心线
        obs_idx = self._closest_index(ox, oy, path)
        px, py = path[obs_idx]
        lat = math.hypot(ox - px, oy - py)
        if lat <= self.lateral_clearance:
            return None
        if lat > self.lateral_clearance + LANE_WIDTH:
            return None
        ox1, oy1 = ox + vx * 1.0, oy + vy * 1.0
        idx1 = self._closest_index(ox1, oy1, path)
        lat1 = math.hypot(ox1 - path[idx1][0], oy1 - path[idx1][1])
        if lat1 >= lat - 0.15:
            return None

        best_d: Optional[float] = None
        # 无 traj 时用 1~2s 外推点判定是否进入本车道
        future_pts: List[Tuple[float, float]] = []
        if traj and len(traj) >= 2:
            for pt in traj[1:]:
                if pt and len(pt) >= 2:
                    future_pts.append((float(pt[0]), float(pt[1])))
        else:
            for k in (1.0, 1.5, 2.0):
                future_pts.append((ox + vx * k, oy + vy * k))

        for fx, fy in future_pts:
            d = self._in_lane_front_distance(x, y, path, closest_idx, fx, fy)
            if d is None:
                continue
            if best_d is None or d < best_d:
                best_d = d
        if best_d is None:
            return None
        v_lead = self._speed_along_path(path, ox, oy, vx, vy)
        return best_d, max(0.0, v_lead), "cutin"

    def _in_lane_front_distance(
        self,
        x: float,
        y: float,
        path: List[Tuple[float, float]],
        closest_idx: int,
        ox: float,
        oy: float,
    ) -> Optional[float]:
        """目标在本车道且在前方时返回纵向间距，否则 None。"""
        obs_idx = self._closest_index(ox, oy, path)
        px, py = path[obs_idx]
        lat = math.hypot(ox - px, oy - py)
        if lat > self.lateral_clearance:
            return None
        if obs_idx < closest_idx:
            return None
        return self._path_arclength_between(path, closest_idx, obs_idx, x, y)

    def _speed_along_path(
        self,
        path: List[Tuple[float, float]],
        ox: float,
        oy: float,
        vx: float,
        vy: float,
    ) -> float:
        """把速度投影到路径切向（前向为正）。"""
        idx = self._closest_index(ox, oy, path)
        if idx >= len(path) - 1:
            idx = max(0, len(path) - 2)
        dx = path[idx + 1][0] - path[idx][0]
        dy = path[idx + 1][1] - path[idx][1]
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

    def _speed_from_obstacle(self, d_obs: float, v_base: float) -> float:
        """静态障碍距离剖面：d>=SLOW→v_base；d<=STOP→0；其间线性。"""
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
