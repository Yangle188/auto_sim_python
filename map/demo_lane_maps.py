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
    城市主干：东西向三车道 + 十字路口停车线 + 东向→北向左转连接道。

    布局（世界坐标，单位 m）:
      东西主路 y=0，x∈[-40, 160]
      南北支路 x=60，y∈[-60, 60]
      路口中心 (60, 0)，停车线在进口道
      中道 UR_EW0_L1 successors = (直行 UR_EW1_L1, 左转 UR_TURN_EL_N)
    """
    lw = LANE_WIDTH
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

    # 南北向进口（装饰/横穿教学）；北向出口接左转连接道
    nb_center = _sample_line(60.0, -60.0, 60.0, -8.0, 10.0)
    sb_center = _sample_line(60.0, 60.0, 60.0, 8.0, 10.0)
    nb_out = _sample_line(60.0, 10.0, 60.0, 60.0, 10.0)
    # 东向中道 → 北向：路口四分之一圆弧（圆心 60,0，半径 10）
    turn_pts: List[Tuple[float, float]] = []
    r_turn = 10.0
    cx, cy = 60.0, 0.0
    for i in range(9):
        th = math.pi - (math.pi / 2.0) * (i / 8.0)  # π(西) → π/2(北)
        turn_pts.append((cx + r_turn * math.cos(th), cy + r_turn * math.sin(th)))

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
    turn = Lane(
        lane_id="UR_TURN_EL_N",
        points=tuple(turn_pts),
        speed_limit=6.0,
        index=1,
        left_marking="virtual",
        right_marking="virtual",
        predecessors=("UR_EW0_L1",),
        successors=("UR_NB_OUT_L1",),
        section_id="UR_TURN",
        name="东向左转连接",
    )
    nb_exit = Lane(
        lane_id="UR_NB_OUT_L1",
        points=tuple(nb_out),
        speed_limit=8.0,
        index=1,
        left_marking="solid",
        right_marking="solid",
        predecessors=("UR_TURN_EL_N",),
        section_id="UR_NB_OUT",
        name="北向出口",
    )

    lanes = dict(lm.lanes)
    lanes[nb.lane_id] = nb
    lanes[sb.lane_id] = sb
    lanes[turn.lane_id] = turn
    lanes[nb_exit.lane_id] = nb_exit

    # 中道：successors = (直行, 左转)；其余进口仍仅直行
    approach = lanes["UR_EW0_L1"]
    through_id = approach.successors[0] if approach.successors else "UR_EW1_L1"
    lanes["UR_EW0_L1"] = Lane(
        lane_id=approach.lane_id,
        points=approach.points,
        speed_limit=approach.speed_limit,
        index=approach.index,
        lane_type=approach.lane_type,
        left_marking=approach.left_marking,
        right_marking=approach.right_marking,
        left_lane_id=approach.left_lane_id,
        right_lane_id=approach.right_lane_id,
        successors=(through_id, "UR_TURN_EL_N"),
        predecessors=approach.predecessors,
        section_id=approach.section_id,
        name=approach.name,
    )

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
        outgoing=("UR_EW2_L1", "UR_NB_OUT_L1"),
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
