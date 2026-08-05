# map/demo_lane_maps.py
"""教学车道级底图：高速三车道走廊 + 城市主干/路口。"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from simulator.config import LANE_WIDTH

from .base_map import BaseMap, MapEdge, MapNode
from .lane_map import Junction, Lane, LaneMap, stitch_lane_sections
from .demo_base_map import build_campus_grid_map


def _sample_line(
    x0: float, y0: float, x1: float, y1: float, step: float = 10.0
) -> List[Tuple[float, float]]:
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return [(x0, y0), (x1, y1)]
    n = max(1, int(math.floor(length / step)))
    pts = [(x0, y0)]
    for k in range(1, n):
        t = k / n
        pts.append((x0 + t * dx, y0 + t * dy))
    pts.append((x1, y1))
    return pts


def build_highway_3lane_map() -> LaneMap:
    """
    高速同向三车道走廊（沿 +x）：
    - 段1 [0,180]: 限速 12 m/s，虚线可换道
    - 段2 [180,280]: 限速 12 m/s，实线禁止换道（教学）
    - 段3 [280,420]: 限速 8 m/s，虚线可换道 + 限速切换

    车道 index：0 左(+y) / 1 中 / 2 右(-y)，道路中心 y=0。
    """
    lw = LANE_WIDTH
    sections = [
        {
            "section_id": "HW_S0",
            "centerline": _sample_line(0.0, 0.0, 180.0, 0.0, 15.0),
            "speed_limit": 12.0,
            "num_lanes": 3,
            "solid_sep": False,
            "name_prefix": "高速前段",
        },
        {
            "section_id": "HW_S1",
            "centerline": _sample_line(180.0, 0.0, 280.0, 0.0, 15.0),
            "speed_limit": 12.0,
            "num_lanes": 3,
            "solid_sep": True,
            "name_prefix": "高速实线段",
        },
        {
            "section_id": "HW_S2",
            "centerline": _sample_line(280.0, 0.0, 420.0, 0.0, 15.0),
            "speed_limit": 8.0,
            "num_lanes": 3,
            "solid_sep": False,
            "name_prefix": "高速后段",
        },
    ]
    lm = stitch_lane_sections(
        "highway_3lane",
        sections,
        title="高速三车道走廊",
        lane_width=lw,
    )
    return lm


def build_highway_3lane_basemap() -> BaseMap:
    """高速走廊对应的简易节点图（算路可选）。"""
    nodes = [
        MapNode("H0", 0.0, 0.0, name="入口"),
        MapNode("H1", 180.0, 0.0, name="实线起点"),
        MapNode("H2", 280.0, 0.0, name="限速点"),
        MapNode("H3", 420.0, 0.0, name="出口"),
    ]
    edges = [
        MapEdge("H0_H1", "H0", "H1", ((0.0, 0.0), (180.0, 0.0)), 12.0, name="高速1"),
        MapEdge("H1_H2", "H1", "H2", ((180.0, 0.0), (280.0, 0.0)), 12.0, name="高速2"),
        MapEdge("H2_H3", "H2", "H3", ((280.0, 0.0), (420.0, 0.0)), 8.0, name="高速3"),
    ]
    return BaseMap("highway_3lane", nodes, edges, title="高速三车道走廊")


def build_urban_arterial_map() -> LaneMap:
    """
    城市主干：东西向双车道（教学挤成 3 显式：左辅感 + 主 + 右）简化为两车道主路；
    为与 LCC 一致用 3 车道（左虚线可换、右缘实线），并含南北向路口连接车道。

    布局（世界坐标，单位 m）:
      东西主路 y=0，x∈[-40, 160]
      南北支路 x=60，y∈[-60, 60]
      路口中心 (60, 0)，停车线在进口道
    """
    lw = LANE_WIDTH
    # 西→东 主路三段（过路口前 / 路口内简化直行 / 过路口后）
    # 城市用 2 条驾驶道：index 0 左、1 右；再加中间视觉？计划要求车道级——用 2 车道更清晰。
    # stitch 要求奇数；用 num_lanes=3 但城市「右道」为主行车道起步。
    west = _sample_line(-40.0, 0.0, 50.0, 0.0, 10.0)
    through = _sample_line(50.0, 0.0, 70.0, 0.0, 5.0)
    east = _sample_line(70.0, 0.0, 160.0, 0.0, 10.0)

    sections = [
        {
            "section_id": "UR_EW0",
            "centerline": west,
            "speed_limit": 10.0,
            "num_lanes": 3,
            "solid_sep": False,
            "name_prefix": "东向进口",
        },
        {
            "section_id": "UR_EW1",
            "centerline": through,
            "speed_limit": 8.0,
            "num_lanes": 3,
            "solid_sep": True,
            "name_prefix": "路口直行",
        },
        {
            "section_id": "UR_EW2",
            "centerline": east,
            "speed_limit": 10.0,
            "num_lanes": 3,
            "solid_sep": False,
            "name_prefix": "东向出口",
        },
    ]
    lm = stitch_lane_sections(
        "urban_arterial",
        sections,
        title="城市主干+路口",
        lane_width=lw,
    )

    # 南北向：单独两条车道（南→北 / 北→南 各取中心），接到路口简化为独立 lane
    nb_center = _sample_line(60.0, -60.0, 60.0, -8.0, 10.0)
    sb_center = _sample_line(60.0, 60.0, 60.0, 8.0, 10.0)
    nb = Lane(
        lane_id="UR_NB_L1",
        points=tuple(nb_center),
        speed_limit=8.0,
        index=1,
        left_marking="solid",
        right_marking="solid",
        section_id="UR_NB",
        name="北向进口",
    )
    sb = Lane(
        lane_id="UR_SB_L1",
        points=tuple(sb_center),
        speed_limit=8.0,
        index=1,
        left_marking="solid",
        right_marking="solid",
        section_id="UR_SB",
        name="南向进口",
    )
    lanes = dict(lm.lanes)
    lanes[nb.lane_id] = nb
    lanes[sb.lane_id] = sb

    stop_w = 1.5 * lw
    junc = Junction(
        junction_id="UR_J0",
        name="十字路口",
        stop_lines=(
            ((50.0, stop_w), (50.0, -stop_w)),
            ((70.0, stop_w), (70.0, -stop_w)),
            ((60.0 - stop_w, -8.0), (60.0 + stop_w, -8.0)),
            ((60.0 - stop_w, 8.0), (60.0 + stop_w, 8.0)),
        ),
        incoming=("UR_EW0_L1", "UR_NB_L1", "UR_SB_L1"),
        outgoing=("UR_EW2_L1",),
    )
    return LaneMap(
        map_id="urban_arterial",
        title="城市主干+路口",
        lanes=lanes,
        junctions={junc.junction_id: junc},
        lane_width=lw,
    )


def build_urban_arterial_basemap() -> BaseMap:
    """城市算路底图：简化十字。"""
    nodes = [
        MapNode("UW", -40.0, 0.0, name="西"),
        MapNode("UJ", 60.0, 0.0, name="路口"),
        MapNode("UE", 160.0, 0.0, name="东"),
        MapNode("US", 60.0, -60.0, name="南"),
        MapNode("UN", 60.0, 60.0, name="北"),
    ]
    edges = [
        MapEdge("UW_UJ", "UW", "UJ", ((-40.0, 0.0), (60.0, 0.0)), 10.0, name="西→路口"),
        MapEdge("UJ_UE", "UJ", "UE", ((60.0, 0.0), (160.0, 0.0)), 10.0, name="路口→东"),
        MapEdge("UE_UJ", "UE", "UJ", ((160.0, 0.0), (60.0, 0.0)), 10.0, name="东→路口"),
        MapEdge("UJ_UW", "UJ", "UW", ((60.0, 0.0), (-40.0, 0.0)), 10.0, name="路口→西"),
        MapEdge("US_UJ", "US", "UJ", ((60.0, -60.0), (60.0, 0.0)), 8.0, name="南→路口"),
        MapEdge("UJ_US", "UJ", "US", ((60.0, 0.0), (60.0, -60.0)), 8.0, name="路口→南"),
        MapEdge("UN_UJ", "UN", "UJ", ((60.0, 60.0), (60.0, 0.0)), 8.0, name="北→路口"),
        MapEdge("UJ_UN", "UJ", "UN", ((60.0, 0.0), (60.0, 60.0)), 8.0, name="路口→北"),
    ]
    return BaseMap("urban_arterial", nodes, edges, title="城市主干+路口")


# ---- registry helpers ----

_LANE_MAP_BUILDERS = {
    "highway_3lane": build_highway_3lane_map,
    "urban_arterial": build_urban_arterial_map,
}

_BASE_MAP_BUILDERS = {
    "campus_grid": build_campus_grid_map,
    "highway_3lane": build_highway_3lane_basemap,
    "urban_arterial": build_urban_arterial_basemap,
}


def list_map_catalog() -> List[Dict[str, str]]:
    return [
        {"map_id": "highway_3lane", "title": "高速三车道走廊", "kind": "highway"},
        {"map_id": "urban_arterial", "title": "城市主干+路口", "kind": "urban"},
        {"map_id": "campus_grid", "title": "校园网格（3×3）", "kind": "campus"},
    ]


def get_lane_map(map_id: Optional[str]) -> Optional[LaneMap]:
    if not map_id:
        return None
    builder = _LANE_MAP_BUILDERS.get(map_id)
    if builder is None:
        return None
    return builder()


def get_base_map(map_id: Optional[str] = None) -> BaseMap:
    """默认返回 campus_grid；未知 id 回退 campus。"""
    mid = map_id or "campus_grid"
    builder = _BASE_MAP_BUILDERS.get(mid)
    if builder is None:
        return build_campus_grid_map()
    return builder()


def default_lane_map() -> LaneMap:
    return build_highway_3lane_map()
