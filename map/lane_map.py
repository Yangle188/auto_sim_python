# map/lane_map.py
"""教学用车道级智驾底图：Lane / 边界 / 邻接 / successor。"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from simulator.config import LANE_WIDTH, NUM_LANES
from simulator.geometry import offset_polyline

Point = Tuple[float, float]
MarkingStyle = str  # solid | dashed | virtual


@dataclass(frozen=True)
class Lane:
    """单条车道：中心线 + 属性 + 拓扑。"""

    lane_id: str
    points: Tuple[Point, ...]
    speed_limit: float
    index: int  # 同向自左向右，0=最左
    lane_type: str = "driving"  # driving | aux | shoulder
    left_marking: MarkingStyle = "dashed"
    right_marking: MarkingStyle = "dashed"
    left_lane_id: Optional[str] = None
    right_lane_id: Optional[str] = None
    successors: Tuple[str, ...] = ()
    predecessors: Tuple[str, ...] = ()
    section_id: str = ""
    name: str = ""

    def __post_init__(self) -> None:
        pts = tuple((float(x), float(y)) for x, y in self.points)
        object.__setattr__(self, "points", pts)
        if len(pts) < 2:
            raise ValueError(f"Lane {self.lane_id}: need at least 2 points")
        if self.speed_limit <= 0.0:
            raise ValueError(f"Lane {self.lane_id}: speed_limit must be > 0")
        lm = (self.left_marking or "dashed").lower()
        rm = (self.right_marking or "dashed").lower()
        for style in (lm, rm):
            if style not in ("solid", "dashed", "virtual"):
                raise ValueError(f"Lane {self.lane_id}: bad marking {style}")
        object.__setattr__(self, "left_marking", lm)
        object.__setattr__(self, "right_marking", rm)

    @property
    def length(self) -> float:
        total = 0.0
        for i in range(len(self.points) - 1):
            x0, y0 = self.points[i]
            x1, y1 = self.points[i + 1]
            total += math.hypot(x1 - x0, y1 - y0)
        return total


@dataclass(frozen=True)
class Junction:
    junction_id: str
    name: str = ""
    # 停车线折线（世界坐标）
    stop_lines: Tuple[Tuple[Point, ...], ...] = ()
    # 连接的进口/出口 lane_id
    incoming: Tuple[str, ...] = ()
    outgoing: Tuple[str, ...] = ()


@dataclass
class LaneMap:
    """车道级底图。"""

    map_id: str
    lanes: Dict[str, Lane]
    title: str = ""
    junctions: Dict[str, Junction] = field(default_factory=dict)
    lane_width: float = LANE_WIDTH

    def __post_init__(self) -> None:
        self.title = self.title or self.map_id
        self.lanes = dict(self.lanes)
        self.junctions = dict(self.junctions)

    def get(self, lane_id: str) -> Lane:
        return self.lanes[lane_id]

    def neighbor(self, lane_id: str, direction: str) -> Optional[Lane]:
        lane = self.lanes.get(lane_id)
        if lane is None:
            return None
        d = direction.lower()
        nid = lane.left_lane_id if d == "left" else lane.right_lane_id if d == "right" else None
        if not nid:
            return None
        return self.lanes.get(nid)

    def crossing_marking(self, lane_id: str, direction: str) -> Optional[str]:
        """变道跨越的边界样式：left → 本车道 left_marking。"""
        lane = self.lanes.get(lane_id)
        if lane is None:
            return None
        d = direction.lower()
        if d == "left":
            return lane.left_marking
        if d == "right":
            return lane.right_marking
        return None

    def find_nearest_lane(
        self,
        x: float,
        y: float,
        *,
        max_dist: float = 8.0,
        lane_type: Optional[str] = "driving",
    ) -> Optional[Lane]:
        best: Optional[Lane] = None
        best_d = float("inf")
        for lane in self.lanes.values():
            if lane_type and lane.lane_type != lane_type:
                continue
            _, lat, _ = project_to_polyline(x, y, lane.points)
            d = abs(lat)
            if d < best_d:
                best_d = d
                best = lane
        if best is None or best_d > max_dist:
            return None
        return best

    def lane_ids_by_index(self, index: int) -> List[str]:
        return [
            lid
            for lid, lane in self.lanes.items()
            if lane.index == index and lane.lane_type == "driving"
        ]

    def follow_lane_chain(self, start_lane_id: str) -> List[str]:
        """沿 successors[0] 向前展开一条车道链（教学高速走廊）。"""
        out: List[str] = []
        seen = set()
        cur = start_lane_id
        while cur and cur not in seen and cur in self.lanes:
            seen.add(cur)
            out.append(cur)
            succs = self.lanes[cur].successors
            cur = succs[0] if succs else ""
        return out

    def chain_centerline(self, lane_ids: Sequence[str]) -> List[Point]:
        pts: List[Point] = []
        for lid in lane_ids:
            lane = self.lanes[lid]
            seg = list(lane.points)
            if pts and seg:
                if math.hypot(seg[0][0] - pts[-1][0], seg[0][1] - pts[-1][1]) < 1e-6:
                    seg = seg[1:]
            pts.extend(seg)
        return pts

    def markings_payload(self) -> List[Dict]:
        """可视化：按车道左右边界挤出标线（同向相邻共享分隔线时去重近似）。"""
        half = 0.5 * float(self.lane_width)
        out: List[Dict] = []
        seen: set = set()
        for lane in self.lanes.values():
            for side, style, lat in (
                ("left", lane.left_marking, half),
                ("right", lane.right_marking, -half),
            ):
                key = (lane.lane_id, side)
                if key in seen:
                    continue
                seen.add(key)
                pts = offset_polyline(lane.points, lat)
                out.append(
                    {
                        "role": f"{lane.lane_id}_{side}",
                        "style": style,
                        "points": [list(p) for p in pts],
                        "source": "lanemap",
                        "lane_id": lane.lane_id,
                    }
                )
        return out

    def to_dict(self) -> dict:
        return {
            "map_id": self.map_id,
            "title": self.title,
            "lane_width": float(self.lane_width),
            "lanes": [
                {
                    "lane_id": lane.lane_id,
                    "points": [[p[0], p[1]] for p in lane.points],
                    "speed_limit": lane.speed_limit,
                    "index": lane.index,
                    "lane_type": lane.lane_type,
                    "left_marking": lane.left_marking,
                    "right_marking": lane.right_marking,
                    "left_lane_id": lane.left_lane_id,
                    "right_lane_id": lane.right_lane_id,
                    "successors": list(lane.successors),
                    "predecessors": list(lane.predecessors),
                    "section_id": lane.section_id,
                    "name": lane.name,
                    "length": lane.length,
                }
                for lane in self.lanes.values()
            ],
            "junctions": [
                {
                    "junction_id": j.junction_id,
                    "name": j.name,
                    "stop_lines": [[[p[0], p[1]] for p in line] for line in j.stop_lines],
                    "incoming": list(j.incoming),
                    "outgoing": list(j.outgoing),
                }
                for j in self.junctions.values()
            ],
            "lane_markings": self.markings_payload(),
        }


def project_to_polyline(
    x: float,
    y: float,
    points: Sequence[Point],
) -> Tuple[float, float, int]:
    """
    投影到折线：返回 (弧长 s, 有符号横向偏移 lat 左正, 段索引)。
    """
    pts = [(float(px), float(py)) for px, py in points]
    if len(pts) < 2:
        if not pts:
            return 0.0, 0.0, 0
        return 0.0, math.hypot(x - pts[0][0], y - pts[0][1]), 0

    best_s = 0.0
    best_lat = 0.0
    best_i = 0
    best_d2 = float("inf")
    cum = 0.0
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        dx, dy = x1 - x0, y1 - y0
        seg_len = math.hypot(dx, dy)
        if seg_len < 1e-12:
            continue
        tx, ty = dx / seg_len, dy / seg_len
        # 左侧法向
        nx, ny = -ty, tx
        t = ((x - x0) * tx + (y - y0) * ty) / seg_len
        t_clamped = max(0.0, min(1.0, t))
        px = x0 + t_clamped * dx
        py = y0 + t_clamped * dy
        d2 = (px - x) ** 2 + (py - y) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best_i = i
            best_s = cum + t_clamped * seg_len
            best_lat = (x - px) * nx + (y - py) * ny
        cum += seg_len
    return best_s, best_lat, best_i


def point_at_s(points: Sequence[Point], s: float) -> Tuple[Point, float]:
    """弧长 s 处的点与航向。"""
    pts = [(float(x), float(y)) for x, y in points]
    if len(pts) < 2:
        p = pts[0] if pts else (0.0, 0.0)
        return p, 0.0
    remain = max(0.0, float(s))
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        seg = math.hypot(x1 - x0, y1 - y0)
        if seg < 1e-12:
            continue
        if remain <= seg or i == len(pts) - 2:
            u = min(1.0, remain / seg)
            yaw = math.atan2(y1 - y0, x1 - x0)
            return (x0 + u * (x1 - x0), y0 + u * (y1 - y0)), yaw
        remain -= seg
    yaw = math.atan2(pts[-1][1] - pts[-2][1], pts[-1][0] - pts[-2][0])
    return pts[-1], yaw


def lanes_from_centerline(
    map_id: str,
    centerline: Sequence[Point],
    *,
    num_lanes: int = NUM_LANES,
    lane_width: float = LANE_WIDTH,
    speed_limit: float = 12.0,
    title: str = "",
    solid_outer: bool = True,
    solid_sep_s_ranges: Optional[Sequence[Tuple[float, float]]] = None,
) -> LaneMap:
    """
    兼容 adapter：以道路中心线为中间车道，挤出平行车道中心线。

    index 自左向右 0..n-1；中间车道 index = n//2。
    solid_sep_s_ranges：弧长区间内分隔线改为实线（整条车道标记统一简化为若区间命中中点则 solid）。
    """
    n = max(1, int(num_lanes))
    if n % 2 == 0:
        n += 1
    half_n = n // 2
    center = [(float(x), float(y)) for x, y in centerline]
    if len(center) < 2:
        raise ValueError("centerline needs >= 2 points")

    # 简化：整条走廊同一 marking；若提供实线区间且中点落入则整段 solid
    sep_style: MarkingStyle = "dashed"
    if solid_sep_s_ranges:
        total = 0.0
        for i in range(len(center) - 1):
            total += math.hypot(center[i + 1][0] - center[i][0], center[i + 1][1] - center[i][1])
        mid_s = 0.5 * total
        for a, b in solid_sep_s_ranges:
            if float(a) <= mid_s <= float(b):
                sep_style = "solid"
                break

    lanes: Dict[str, Lane] = {}
    lane_ids: List[str] = []
    for k in range(half_n, -half_n - 1, -1):
        # k: +half_n 最左 ... 0 中 ... -half_n 最右
        idx = half_n - k  # 0..n-1 left to right
        lid = f"{map_id}_L{idx}"
        lane_ids.append(lid)
        pts = center if k == 0 else offset_polyline(center, k * float(lane_width))
        left_m: MarkingStyle = "solid" if (solid_outer and idx == 0) else sep_style
        right_m: MarkingStyle = "solid" if (solid_outer and idx == n - 1) else sep_style
        lanes[lid] = Lane(
            lane_id=lid,
            points=tuple(pts),
            speed_limit=float(speed_limit),
            index=idx,
            lane_type="driving",
            left_marking=left_m,
            right_marking=right_m,
            section_id=f"{map_id}_S0",
            name=f"车道{idx}",
        )

    # 邻接
    for i, lid in enumerate(lane_ids):
        left_id = lane_ids[i - 1] if i > 0 else None
        right_id = lane_ids[i + 1] if i < len(lane_ids) - 1 else None
        lane = lanes[lid]
        lanes[lid] = Lane(
            lane_id=lane.lane_id,
            points=lane.points,
            speed_limit=lane.speed_limit,
            index=lane.index,
            lane_type=lane.lane_type,
            left_marking=lane.left_marking,
            right_marking=lane.right_marking,
            left_lane_id=left_id,
            right_lane_id=right_id,
            successors=(),
            predecessors=(),
            section_id=lane.section_id,
            name=lane.name,
        )

    return LaneMap(
        map_id=map_id,
        title=title or map_id,
        lanes=lanes,
        lane_width=float(lane_width),
    )


def stitch_lane_sections(
    map_id: str,
    sections: Sequence[Dict],
    *,
    title: str = "",
    lane_width: float = LANE_WIDTH,
) -> LaneMap:
    """
    将多段同向多车道路段接成 LaneMap。

    每个 section dict:
      section_id, centerline, speed_limit, num_lanes,
      solid_sep (bool, 可选), name_prefix (可选)
    相邻 section 同 index 车道互相 successor/predecessor。
    """
    all_lanes: Dict[str, Lane] = {}
    section_lane_ids: List[List[str]] = []

    for si, sec in enumerate(sections):
        sid = str(sec["section_id"])
        n = int(sec.get("num_lanes", NUM_LANES))
        if n % 2 == 0:
            n += 1
        half_n = n // 2
        center = list(sec["centerline"])
        speed = float(sec["speed_limit"])
        solid_sep = bool(sec.get("solid_sep", False))
        sep_style: MarkingStyle = "solid" if solid_sep else "dashed"
        prefix = str(sec.get("name_prefix", sid))
        ids: List[str] = []
        for k in range(half_n, -half_n - 1, -1):
            idx = half_n - k
            lid = f"{sid}_L{idx}"
            ids.append(lid)
            pts = center if k == 0 else offset_polyline(center, k * float(lane_width))
            left_m: MarkingStyle = "solid" if idx == 0 else sep_style
            right_m: MarkingStyle = "solid" if idx == n - 1 else sep_style
            all_lanes[lid] = Lane(
                lane_id=lid,
                points=tuple((float(x), float(y)) for x, y in pts),
                speed_limit=speed,
                index=idx,
                left_marking=left_m,
                right_marking=right_m,
                section_id=sid,
                name=f"{prefix}-车道{idx}",
            )
        # 邻接
        for i, lid in enumerate(ids):
            lane = all_lanes[lid]
            all_lanes[lid] = Lane(
                lane_id=lane.lane_id,
                points=lane.points,
                speed_limit=lane.speed_limit,
                index=lane.index,
                lane_type=lane.lane_type,
                left_marking=lane.left_marking,
                right_marking=lane.right_marking,
                left_lane_id=ids[i - 1] if i > 0 else None,
                right_lane_id=ids[i + 1] if i < len(ids) - 1 else None,
                successors=(),
                predecessors=(),
                section_id=lane.section_id,
                name=lane.name,
            )
        section_lane_ids.append(ids)

    # 段间 successor
    for si in range(len(section_lane_ids) - 1):
        a_ids = section_lane_ids[si]
        b_ids = section_lane_ids[si + 1]
        for lid_a, lid_b in zip(a_ids, b_ids):
            la = all_lanes[lid_a]
            lb = all_lanes[lid_b]
            all_lanes[lid_a] = Lane(
                lane_id=la.lane_id,
                points=la.points,
                speed_limit=la.speed_limit,
                index=la.index,
                lane_type=la.lane_type,
                left_marking=la.left_marking,
                right_marking=la.right_marking,
                left_lane_id=la.left_lane_id,
                right_lane_id=la.right_lane_id,
                successors=(lid_b,),
                predecessors=la.predecessors,
                section_id=la.section_id,
                name=la.name,
            )
            all_lanes[lid_b] = Lane(
                lane_id=lb.lane_id,
                points=lb.points,
                speed_limit=lb.speed_limit,
                index=lb.index,
                lane_type=lb.lane_type,
                left_marking=lb.left_marking,
                right_marking=lb.right_marking,
                left_lane_id=lb.left_lane_id,
                right_lane_id=lb.right_lane_id,
                successors=lb.successors,
                predecessors=(lid_a,),
                section_id=lb.section_id,
                name=lb.name,
            )

    return LaneMap(
        map_id=map_id,
        title=title or map_id,
        lanes=all_lanes,
        lane_width=float(lane_width),
    )
