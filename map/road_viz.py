# map/road_viz.py
"""底图路网可视化：为每条无向路段挤出多车道标线。"""
from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from simulator.config import LANE_WIDTH, NUM_LANES
from simulator.geometry import multi_lane_boundaries

from .base_map import BaseMap


def base_map_lane_markings(
    base: BaseMap,
    lane_width: float = LANE_WIDTH,
    num_lanes: int = NUM_LANES,
) -> List[Dict[str, Any]]:
    """
    对底图每条无向边生成三车道标线（实线外缘 + 虚线分隔）。

    仅用于可视化；控制/规划仍只跟导航 Route 中心线。
    """
    seen: Set[Tuple[str, str]] = set()
    out: List[Dict[str, Any]] = []
    for edge in base.edges.values():
        a, b = edge.from_node, edge.to_node
        key = (a, b) if a <= b else (b, a)
        if key in seen:
            continue
        seen.add(key)
        lane = multi_lane_boundaries(
            edge.points, lane_width=lane_width, num_lanes=num_lanes
        )
        for m in lane.get("markings") or []:
            out.append(
                {
                    "role": f"net_{edge.edge_id}_{m.get('role', '')}",
                    "style": m.get("style", "solid"),
                    "points": [list(p) for p in (m.get("points") or [])],
                    "source": "basemap",
                }
            )
    return out
