# map/map_manager.py
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .config import SPEED_LOOKAHEAD_DIST
from .route import Route


@dataclass
class _Segment:
    """全局弧长上的一段限速区间 [s0, s1)。"""

    s0: float
    s1: float
    speed_limit: float
    link_id: str


class MapManager:
    """路线下发与限速查询。"""

    def __init__(self) -> None:
        self._route: Optional[Route] = None
        self._waypoints: List[Tuple[float, float]] = []
        self._segments: List[_Segment] = []
        self._cum_s: List[float] = []  # 与 waypoints 对齐的累计弧长

    def clear_route(self) -> None:
        self._route = None
        self._waypoints = []
        self._segments = []
        self._cum_s = []

    def set_route(self, route: Route) -> None:
        if not isinstance(route, Route):
            raise TypeError("route must be a Route")
        self._route = route
        self._rebuild_cache()

    @property
    def route(self) -> Optional[Route]:
        return self._route

    def get_waypoints(self) -> List[Tuple[float, float]]:
        return list(self._waypoints)

    def get_route_links(self) -> List[dict]:
        """可视化用：各 link 的点列与限速。"""
        if self._route is None:
            return []
        return [
            {
                "link_id": link.link_id,
                "points": [[float(x), float(y)] for x, y in link.points],
                "speed_limit": float(link.speed_limit),
                "name": getattr(link, "name", "") or "",
                "road_class": getattr(link, "road_class", "main") or "main",
                "maneuver": getattr(link, "maneuver", "straight") or "straight",
            }
            for link in self._route.links
        ]

    def get_speed_limit(self, x: float, y: float) -> Optional[float]:
        """投影到路线最近点所属 link 的限速；无路线返回 None。"""
        if not self._segments:
            return None
        s, _ = self._project_arclength(x, y)
        return self._speed_at_s(s)

    def get_speed_limit_ahead(
        self,
        x: float,
        y: float,
        lookahead: float = SPEED_LOOKAHEAD_DIST,
    ) -> Optional[float]:
        """
        当前弧长向前 lookahead 米内的最低限速（含当前段）。
        无路线返回 None。
        """
        if not self._segments:
            return None
        s, _ = self._project_arclength(x, y)
        s_end = s + max(0.0, float(lookahead))
        v = self._speed_at_s(s)
        for seg in self._segments:
            if seg.s1 <= s:
                continue
            if seg.s0 >= s_end:
                break
            v = min(v, seg.speed_limit)
        return v

    def _rebuild_cache(self) -> None:
        assert self._route is not None
        waypoints: List[Tuple[float, float]] = []
        segments: List[_Segment] = []
        s_cursor = 0.0

        for link in self._route.links:
            pts = list(link.points)
            if waypoints:
                # 相邻重复端点去重
                if math.hypot(pts[0][0] - waypoints[-1][0], pts[0][1] - waypoints[-1][1]) < 1e-9:
                    pts = pts[1:]
            if not pts:
                continue

            s0 = s_cursor
            if not waypoints:
                waypoints.append(pts[0])
                start_i = 1
            else:
                start_i = 0

            for i in range(start_i, len(pts)):
                x0, y0 = waypoints[-1]
                x1, y1 = pts[i]
                s_cursor += math.hypot(x1 - x0, y1 - y0)
                waypoints.append((x1, y1))

            segments.append(
                _Segment(
                    s0=s0,
                    s1=s_cursor,
                    speed_limit=link.speed_limit,
                    link_id=link.link_id,
                )
            )

        self._waypoints = waypoints
        self._segments = segments
        self._cum_s = self._build_cum_s(waypoints)

    @staticmethod
    def _build_cum_s(waypoints: List[Tuple[float, float]]) -> List[float]:
        if not waypoints:
            return []
        cum = [0.0]
        for i in range(len(waypoints) - 1):
            x0, y0 = waypoints[i]
            x1, y1 = waypoints[i + 1]
            cum.append(cum[-1] + math.hypot(x1 - x0, y1 - y0))
        return cum

    def _project_arclength(self, x: float, y: float) -> Tuple[float, int]:
        """
        投影到折线最近点，返回弧长 s 与所在段起点索引。
        """
        if not self._waypoints:
            return 0.0, 0
        if len(self._waypoints) == 1:
            return 0.0, 0

        best_s = 0.0
        best_i = 0
        best_d2 = float("inf")
        for i in range(len(self._waypoints) - 1):
            x0, y0 = self._waypoints[i]
            x1, y1 = self._waypoints[i + 1]
            dx, dy = x1 - x0, y1 - y0
            seg_len2 = dx * dx + dy * dy
            if seg_len2 < 1e-18:
                t = 0.0
                px, py = x0, y0
            else:
                t = ((x - x0) * dx + (y - y0) * dy) / seg_len2
                t = max(0.0, min(1.0, t))
                px = x0 + t * dx
                py = y0 + t * dy
            d2 = (px - x) ** 2 + (py - y) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best_i = i
                best_s = self._cum_s[i] + t * math.sqrt(seg_len2)
        return best_s, best_i

    def _speed_at_s(self, s: float) -> float:
        """弧长 s 所属段限速；区间为 [s0, s1)，终点归入最后一段。"""
        if not self._segments:
            return 0.0
        for seg in self._segments:
            if s < seg.s1:
                return seg.speed_limit
        return self._segments[-1].speed_limit
