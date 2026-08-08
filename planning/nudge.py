# planning/nudge.py
"""同车道简单绕障：对 LCC 路径做短距横向弓形偏移（教学用，非完整变道）。"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from map.lane_map import LaneMap, point_at_s, project_to_polyline
from simulator.config import LANE_WIDTH

from .config import (
    DEFAULT_LEAD_HALF_LENGTH,
    EGO_FRONT_LENGTH,
    NUDGE_APPROACH_S,
    NUDGE_DONE_PAST_S,
    NUDGE_HOLD_S,
    NUDGE_LAT_FRAC,
    NUDGE_RETURN_S,
    NUDGE_STATIC_SPEED,
    NUDGE_TRIGGER_MAX,
    NUDGE_TRIGGER_MIN,
    OBSTACLE_LATERAL_CLEARANCE,
    PATH_RESOLUTION,
)

Point = Tuple[float, float]

NUDGE_IDLE = "idle"
NUDGE_ACTIVE = "nudging"
NUDGE_DONE = "done"


def _path_length(points: Sequence[Point]) -> float:
    total = 0.0
    for i in range(len(points) - 1):
        total += math.hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1])
    return total


def _envelope(s: float, s0: float, s1: float, s2: float, s3: float) -> float:
    """梯形包络：0→1→1→0。"""
    if s <= s0 or s >= s3:
        return 0.0
    if s < s1:
        return (s - s0) / max(1e-6, s1 - s0)
    if s <= s2:
        return 1.0
    return max(0.0, (s3 - s) / max(1e-6, s3 - s2))


def _parse_static_lead(lead: Any) -> Optional[Tuple[float, float, float]]:
    """返回 (x, y, half_length) 若视为静止障碍。"""
    if isinstance(lead, dict):
        x = lead.get("x")
        y = lead.get("y")
        vx = float(lead.get("vx", 0.0) or 0.0)
        vy = float(lead.get("vy", 0.0) or 0.0)
        half = 0.5 * float(lead.get("height", DEFAULT_LEAD_HALF_LENGTH * 2) or DEFAULT_LEAD_HALF_LENGTH * 2)
    else:
        x = getattr(lead, "x", None)
        y = getattr(lead, "y", None)
        vx = float(getattr(lead, "vx", 0.0) or 0.0)
        vy = float(getattr(lead, "vy", 0.0) or 0.0)
        half = 0.5 * float(getattr(lead, "height", DEFAULT_LEAD_HALF_LENGTH * 2) or DEFAULT_LEAD_HALF_LENGTH * 2)
    if x is None or y is None:
        return None
    if math.hypot(vx, vy) > NUDGE_STATIC_SPEED:
        return None
    return float(x), float(y), max(0.5, half)


@dataclass
class NudgeController:
    """ACTIVE + LC idle 时，对本车道静止障碍做短距横向绕行。"""

    enabled: bool = True
    state: str = NUDGE_IDLE
    side: str = ""  # left | right
    _path: List[Point] = field(default_factory=list)
    _s_obs: float = 0.0
    _logged_start: bool = False

    def reset(self) -> None:
        self.state = NUDGE_IDLE
        self.side = ""
        self._path = []
        self._s_obs = 0.0
        self._logged_start = False

    def status_payload(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "side": self.side or None,
            "enabled": bool(self.enabled),
        }

    def current_path(self) -> Optional[List[Point]]:
        if self.state == NUDGE_ACTIVE and len(self._path) >= 2:
            return list(self._path)
        return None

    def tick(
        self,
        *,
        active: bool,
        lc_idle: bool,
        ego_xy: Tuple[float, float],
        lcc_path: Sequence[Point],
        leads: Sequence[Any],
        lane_map: LaneMap,
        ego_lane_id: str,
    ) -> Optional[str]:
        """
        推进状态；返回事件 code 文案后缀：None | "start:left" | "done"。
        """
        if not self.enabled or not active or not lc_idle or len(lcc_path) < 2:
            if self.state == NUDGE_ACTIVE:
                self.reset()
            return None

        ego_s, _, _ = project_to_polyline(ego_xy[0], ego_xy[1], lcc_path)

        if self.state == NUDGE_ACTIVE:
            if ego_s > self._s_obs + NUDGE_DONE_PAST_S:
                self.state = NUDGE_DONE
                self._path = []
                return "done"
            # 持续刷新弓形路径（LCC 可能随 successor 更新）
            self._path = self._build_path(lcc_path, ego_s, self._s_obs, self.side)
            return None

        if self.state == NUDGE_DONE:
            return None

        # idle → 寻找静止本车道障碍
        best = None
        best_d = float("inf")
        for lead in leads:
            parsed = _parse_static_lead(lead)
            if parsed is None:
                continue
            ox, oy, half = parsed
            s_obs, lat, _ = project_to_polyline(ox, oy, lcc_path)
            if abs(lat) > OBSTACLE_LATERAL_CLEARANCE:
                continue
            # 保险杠净空
            d_gap = (s_obs - ego_s) - EGO_FRONT_LENGTH - half
            if d_gap < NUDGE_TRIGGER_MIN or d_gap > NUDGE_TRIGGER_MAX:
                continue
            if d_gap < best_d:
                best_d = d_gap
                best = (s_obs, lat)

        if best is None:
            return None

        s_obs, obs_lat = best
        side = self._pick_side(lane_map, ego_lane_id, obs_lat)
        if side is None:
            return None

        self.state = NUDGE_ACTIVE
        self.side = side
        self._s_obs = s_obs
        self._path = self._build_path(lcc_path, ego_s, s_obs, side)
        return f"start:{side}"

    def _pick_side(
        self, lane_map: LaneMap, ego_lane_id: str, obs_lat: float
    ) -> Optional[str]:
        """优先邻道空闲侧；否则绕开障碍所在侧（obs 偏右则向左绕）。"""
        left = lane_map.neighbor(ego_lane_id, "left")
        right = lane_map.neighbor(ego_lane_id, "right")
        # 有邻道时优先左（教学习惯）
        if left is not None and right is None:
            return "left"
        if right is not None and left is None:
            return "right"
        if left is not None and right is not None:
            return "left" if obs_lat <= 0 else "right"
        # 无邻道：仍允许同车道内弓形（朝远离障碍横向）
        return "left" if obs_lat <= 0 else "right"

    def _build_path(
        self,
        lcc: Sequence[Point],
        ego_s: float,
        s_obs: float,
        side: str,
    ) -> List[Point]:
        sign = 1.0 if side == "left" else -1.0
        lat_amp = sign * NUDGE_LAT_FRAC * float(LANE_WIDTH)
        s0 = s_obs - NUDGE_APPROACH_S
        s1 = s_obs - 0.25 * NUDGE_HOLD_S
        s2 = s_obs + 0.75 * NUDGE_HOLD_S
        s3 = s_obs + NUDGE_RETURN_S
        total = _path_length(lcc)
        step = max(0.5, PATH_RESOLUTION * 0.5)
        s = max(0.0, ego_s - 2.0)
        out: List[Point] = []
        while s <= total + 1e-6:
            (x, y), yaw = point_at_s(lcc, s)
            e = _envelope(s, s0, s1, s2, s3)
            lat = lat_amp * e
            nx, ny = -math.sin(yaw), math.cos(yaw)
            out.append((x + nx * lat, y + ny * lat))
            s += step
        if len(out) < 2 and len(lcc) >= 2:
            return [(float(p[0]), float(p[1])) for p in lcc]
        return out
