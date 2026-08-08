# planning/lane_change.py
"""拨杆变道状态机：Idle → Changing → Completed/Abort。"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from map.lane_map import LaneMap, point_at_s, project_to_polyline
from simulator.config import LANE_WIDTH

from .config import PATH_RESOLUTION

Point = Tuple[float, float]

LC_IDLE = "idle"
LC_CHANGING = "changing"
LC_ABORTING = "aborting"

# 变道参数（教学默认，可被构造参数覆盖）
DEFAULT_MIN_SPEED = 3.0
DEFAULT_MAX_SPEED = 30.0
DEFAULT_TRANSITION_TIME = 3.0  # s，过渡时长基准（更短 → 横向更明显）
DEFAULT_MIN_TRANSITION_S = 12.0
DEFAULT_MAX_TRANSITION_S = 32.0
DEFAULT_SETTLE_LAT = 0.55  # m
DEFAULT_TIMEOUT_S = 12.0
DEFAULT_CLEAR_AHEAD = 25.0
DEFAULT_CLEAR_LAT = 0.55 * LANE_WIDTH


@dataclass
class LaneChangeResult:
    ok: bool
    reason: str = ""
    msg: str = ""
    path: Optional[List[Point]] = None
    ego_lane_id: Optional[str] = None
    target_lane_id: Optional[str] = None
    state: str = LC_IDLE


@dataclass
class LaneChangeController:
    """横向变道：生成过渡路径供 Pure Pursuit 跟踪。"""

    lane_map: LaneMap
    min_speed: float = DEFAULT_MIN_SPEED
    max_speed: float = DEFAULT_MAX_SPEED
    transition_time: float = DEFAULT_TRANSITION_TIME
    min_transition_s: float = DEFAULT_MIN_TRANSITION_S
    max_transition_s: float = DEFAULT_MAX_TRANSITION_S
    settle_lat: float = DEFAULT_SETTLE_LAT
    timeout_s: float = DEFAULT_TIMEOUT_S
    clear_ahead: float = DEFAULT_CLEAR_AHEAD
    clear_lat: float = DEFAULT_CLEAR_LAT
    path_resolution: float = PATH_RESOLUTION

    prefer_maneuver: Optional[str] = None  # straight|left|right；多 successor 时选链

    state: str = LC_IDLE
    ego_lane_id: str = ""
    target_lane_id: Optional[str] = None
    direction: str = ""
    _path: List[Point] = field(default_factory=list)
    _elapsed: float = 0.0
    _transition_s: float = DEFAULT_MIN_TRANSITION_S

    def reset(self, ego_lane_id: str) -> None:
        self.state = LC_IDLE
        self.ego_lane_id = ego_lane_id
        self.target_lane_id = None
        self.direction = ""
        self._path = []
        self._elapsed = 0.0

    def set_prefer_maneuver(self, maneuver: Optional[str]) -> None:
        m = (maneuver or "straight").lower()
        if m not in ("straight", "left", "right", "merge", "diverge"):
            m = "straight"
        self.prefer_maneuver = m

    def _chain(self, lane_id: str) -> List[str]:
        return self.lane_map.follow_lane_chain(
            lane_id, prefer_maneuver=self.prefer_maneuver or "straight"
        )

    def set_lane_map(self, lane_map: LaneMap, ego_lane_id: str) -> None:
        self.lane_map = lane_map
        self.reset(ego_lane_id)

    def status_payload(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "ego_lane_id": self.ego_lane_id,
            "target_lane_id": self.target_lane_id,
            "direction": self.direction,
            "lane_index": int(self.lane_map.lanes[self.ego_lane_id].index)
            if self.ego_lane_id in self.lane_map.lanes
            else None,
        }

    def request(
        self,
        direction: str,
        *,
        speed: float,
        ego_xy: Tuple[float, float],
        leads: Sequence[Any] = (),
        active: bool = True,
    ) -> LaneChangeResult:
        d = direction.lower().strip()
        if d not in ("left", "right"):
            return LaneChangeResult(False, "bad_direction", "变道方向无效")
        if not active:
            return LaneChangeResult(False, "not_active", "请先激活智驾功能")
        if self.state != LC_IDLE:
            return LaneChangeResult(False, "busy", "变道进行中")
        if not (self.min_speed <= float(speed) <= self.max_speed):
            return LaneChangeResult(
                False, "speed", f"车速需在 {self.min_speed:.0f}~{self.max_speed:.0f} m/s"
            )

        ego_lane = self.lane_map.lanes.get(self.ego_lane_id)
        if ego_lane is None:
            return LaneChangeResult(False, "no_lane", "当前车道未知")

        marking = self.lane_map.crossing_marking(self.ego_lane_id, d)
        if marking == "solid":
            return LaneChangeResult(False, "solid", "实线禁止变道")

        target = self.lane_map.neighbor(self.ego_lane_id, d)
        if target is None:
            return LaneChangeResult(False, "no_neighbor", "无邻道可换")

        if not self._target_clear(target, ego_xy, leads):
            return LaneChangeResult(False, "occupied", "目标车道有车，无法变道")

        chain = self._chain(target.lane_id)
        target_line = self.lane_map.chain_centerline(chain)
        ego_chain = self._chain(self.ego_lane_id)
        ego_line = self.lane_map.chain_centerline(ego_chain)
        if len(target_line) < 2 or len(ego_line) < 2:
            return LaneChangeResult(False, "geometry", "车道几何不足")

        s_ego, _, _ = project_to_polyline(ego_xy[0], ego_xy[1], ego_line)
        trans_s = float(speed) * self.transition_time
        trans_s = max(self.min_transition_s, min(self.max_transition_s, trans_s))
        path = self._build_transition_path(ego_line, target_line, s_ego, trans_s)
        if len(path) < 2:
            return LaneChangeResult(False, "path", "变道路径生成失败")

        self.state = LC_CHANGING
        self.direction = d
        self.target_lane_id = target.lane_id
        self._path = path
        self._elapsed = 0.0
        self._transition_s = trans_s
        return LaneChangeResult(
            True,
            "ok",
            "变道中" if d == "left" else "变道中",
            path=path,
            ego_lane_id=self.ego_lane_id,
            target_lane_id=target.lane_id,
            state=self.state,
        )

    def tick(
        self,
        dt: float,
        ego_xy: Tuple[float, float],
        leads: Sequence[Any] = (),
    ) -> LaneChangeResult:
        if self.state == LC_IDLE:
            return LaneChangeResult(True, "idle", state=LC_IDLE, ego_lane_id=self.ego_lane_id)

        self._elapsed += float(dt)
        target_id = self.target_lane_id or self.ego_lane_id
        target = self.lane_map.lanes.get(target_id)
        if target is None:
            self.state = LC_IDLE
            return LaneChangeResult(False, "lost_target", "目标车道丢失", state=LC_IDLE)

        chain = self._chain(target.lane_id)
        target_line = self.lane_map.chain_centerline(chain)
        _, lat, _ = project_to_polyline(ego_xy[0], ego_xy[1], target_line)

        if self.state == LC_CHANGING:
            # 目标车道突然被近距占用 → 中止（仍继续当前过渡路径回中或保持）
            if not self._target_clear(target, ego_xy, leads, ahead=12.0):
                self.state = LC_ABORTING
                return LaneChangeResult(
                    False,
                    "abort_occupied",
                    "变道取消：目标车道占用",
                    path=self._path,
                    ego_lane_id=self.ego_lane_id,
                    target_lane_id=self.target_lane_id,
                    state=self.state,
                )
            if self._elapsed > self.timeout_s:
                self.state = LC_ABORTING
                return LaneChangeResult(
                    False,
                    "timeout",
                    "变道取消：超时",
                    path=self._path,
                    state=self.state,
                )
            if abs(lat) <= self.settle_lat and self._elapsed > 0.35 * self.transition_time:
                # 完成：提交到当前位置最近的同向目标车道（跨 section）
                self.ego_lane_id = self._resolve_lane_at(
                    ego_xy, preferred_index=int(target.index)
                ) or target.lane_id
                self.state = LC_IDLE
                self.target_lane_id = None
                self.direction = ""
                self._path = []
                return LaneChangeResult(
                    True,
                    "completed",
                    "变道完成",
                    ego_lane_id=self.ego_lane_id,
                    state=LC_IDLE,
                )
            return LaneChangeResult(
                True,
                "changing",
                "变道中",
                path=self._path,
                ego_lane_id=self.ego_lane_id,
                target_lane_id=self.target_lane_id,
                state=LC_CHANGING,
            )

        # ABORTING：回到原车道中心线
        if self.state == LC_ABORTING:
            ego_lane = self.lane_map.lanes.get(self.ego_lane_id)
            if ego_lane is None:
                self.state = LC_IDLE
                return LaneChangeResult(False, "abort_done", state=LC_IDLE)
            ego_line = self.lane_map.chain_centerline(
                self._chain(ego_lane.lane_id)
            )
            _, lat_e, _ = project_to_polyline(ego_xy[0], ego_xy[1], ego_line)
            if abs(lat_e) <= self.settle_lat or self._elapsed > self.timeout_s + 3.0:
                self.state = LC_IDLE
                self.target_lane_id = None
                self.direction = ""
                self._path = []
                return LaneChangeResult(
                    True, "aborted", "变道已取消", ego_lane_id=self.ego_lane_id, state=LC_IDLE
                )
            # 使用原车道链作为路径
            self._path = ego_line
            return LaneChangeResult(
                True,
                "aborting",
                "变道取消中",
                path=self._path,
                ego_lane_id=self.ego_lane_id,
                state=LC_ABORTING,
            )

        return LaneChangeResult(True, "idle", state=self.state, ego_lane_id=self.ego_lane_id)

    def current_path_override(self) -> Optional[List[Point]]:
        if self.state in (LC_CHANGING, LC_ABORTING) and self._path:
            return list(self._path)
        return None

    def lcc_path(self) -> List[Point]:
        """当前车道链中心线（LCC）。"""
        if self.ego_lane_id not in self.lane_map.lanes:
            return []
        return self.lane_map.chain_centerline(
            self._chain(self.ego_lane_id)
        )

    def _target_clear(
        self,
        target_lane,
        ego_xy: Tuple[float, float],
        leads: Sequence[Any],
        ahead: Optional[float] = None,
    ) -> bool:
        ahead = self.clear_ahead if ahead is None else ahead
        line = self.lane_map.chain_centerline(
            self._chain(target_lane.lane_id)
        )
        if len(line) < 2:
            return True
        ego_s, _, _ = project_to_polyline(ego_xy[0], ego_xy[1], line)
        for lead in leads:
            lx = float(lead.get("x", 0.0) if isinstance(lead, dict) else getattr(lead, "x", 0.0))
            ly = float(lead.get("y", 0.0) if isinstance(lead, dict) else getattr(lead, "y", 0.0))
            s, lat, _ = project_to_polyline(lx, ly, line)
            if abs(lat) > self.clear_lat:
                continue
            ds = s - ego_s
            if -5.0 <= ds <= ahead:
                return False
        return True

    def _build_transition_path(
        self,
        ego_line: Sequence[Point],
        target_line: Sequence[Point],
        s0: float,
        trans_s: float,
    ) -> List[Point]:
        """在弧长 [s0, s0+trans_s] 内用 smoothstep 混合两中心线，其后跟目标车道。"""
        res = max(0.5, float(self.path_resolution))
        total_t = 0.0
        for i in range(len(target_line) - 1):
            total_t += math.hypot(
                target_line[i + 1][0] - target_line[i][0],
                target_line[i + 1][1] - target_line[i][1],
            )
        s_end = min(total_t, s0 + max(trans_s, 5.0) + 60.0)
        out: List[Point] = []
        # 从自车后方一点开始，便于 Pure Pursuit 投影
        s = max(0.0, s0 - 8.0)
        while s <= s_end + 1e-6:
            pe, _ = point_at_s(ego_line, max(s, s0) if s < s0 else s)
            pt, _ = point_at_s(target_line, max(s, s0) if s < s0 else s)
            # 车后方仍贴原车道，前方再过渡
            if s <= s0:
                u = 0.0
                pe, _ = point_at_s(ego_line, s)
                x, y = pe[0], pe[1]
            elif s >= s0 + trans_s:
                u = 1.0
                pt, _ = point_at_s(target_line, s)
                x, y = pt[0], pt[1]
            else:
                t = (s - s0) / max(trans_s, 1e-6)
                # 更早偏向目标车道（smoothstep 前移）
                u = t * t * (3.0 - 2.0 * t)
                u = min(1.0, u * 1.15)
                pe, _ = point_at_s(ego_line, s)
                pt, _ = point_at_s(target_line, s)
                x = pe[0] + u * (pt[0] - pe[0])
                y = pe[1] + u * (pt[1] - pe[1])
            if not out or math.hypot(x - out[-1][0], y - out[-1][1]) > 0.15:
                out.append((x, y))
            s += res
        return out

    def _resolve_lane_at(
        self,
        ego_xy: Tuple[float, float],
        *,
        preferred_index: Optional[int] = None,
    ) -> Optional[str]:
        """按位置选择最近车道；可限制为指定 index（变道完成后锁定目标道）。"""
        best_id: Optional[str] = None
        best_d = float("inf")
        x, y = float(ego_xy[0]), float(ego_xy[1])
        for lane in self.lane_map.lanes.values():
            if preferred_index is not None and lane.index != preferred_index:
                continue
            if lane.lane_type != "driving":
                continue
            s, _lat, _ = project_to_polyline(x, y, lane.points)
            (px, py), _ = point_at_s(lane.points, s)
            d = math.hypot(x - px, y - py)
            if d < best_d:
                best_d = d
                best_id = lane.lane_id
        return best_id
