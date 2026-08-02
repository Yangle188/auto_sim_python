# map/router.py
"""底图最短路 → 导航 Route（复用 Link）。"""
from __future__ import annotations

import heapq
from typing import Dict, List, Optional, Tuple

from .base_map import BaseMap, MapEdge
from .link import Link
from .route import Route


def _dijkstra(
    base: BaseMap, start_id: str, goal_id: str
) -> Optional[List[MapEdge]]:
    if start_id not in base.nodes or goal_id not in base.nodes:
        return None
    if start_id == goal_id:
        return []

    dist: Dict[str, float] = {start_id: 0.0}
    prev_edge: Dict[str, MapEdge] = {}
    pq: List[Tuple[float, str]] = [(0.0, start_id)]

    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, float("inf")):
            continue
        if u == goal_id:
            break
        for edge in base.outgoing(u):
            v = edge.to_node
            nd = d + edge.length
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev_edge[v] = edge
                heapq.heappush(pq, (nd, v))

    if goal_id not in prev_edge:
        return None

    path: List[MapEdge] = []
    cur = goal_id
    while cur != start_id:
        edge = prev_edge[cur]
        path.append(edge)
        cur = edge.from_node
    path.reverse()
    return path


def plan_route(
    base: BaseMap,
    *,
    start_node: Optional[str] = None,
    end_node: Optional[str] = None,
    start_xy: Optional[Tuple[float, float]] = None,
    end_xy: Optional[Tuple[float, float]] = None,
    route_id: Optional[str] = None,
    snap_max_dist: float = 25.0,
) -> Route:
    """
    在底图上规划最短路径，输出可下发的 Route。

    可传节点 ID，或世界坐标（自动吸附最近节点）。
    """
    if start_node is None:
        if start_xy is None:
            raise ValueError("需要 start_node 或 start_xy")
        sn = base.nearest_node(start_xy[0], start_xy[1], max_dist=snap_max_dist)
        if sn is None:
            raise ValueError("起点无法吸附到路网节点")
        start_node = sn.node_id
    if end_node is None:
        if end_xy is None:
            raise ValueError("需要 end_node 或 end_xy")
        en = base.nearest_node(end_xy[0], end_xy[1], max_dist=snap_max_dist)
        if en is None:
            raise ValueError("终点无法吸附到路网节点")
        end_node = en.node_id

    if start_node == end_node:
        raise ValueError("起点与终点不能相同")

    edges = _dijkstra(base, start_node, end_node)
    if edges is None:
        raise ValueError(f"无法从 {start_node} 到达 {end_node}")
    if not edges:
        raise ValueError("路径为空")

    links = tuple(
        Link(
            edge.edge_id,
            edge.points,
            edge.speed_limit,
            name=edge.name or edge.edge_id,
            road_class=edge.road_class,
            maneuver=edge.maneuver,
        )
        for edge in edges
    )
    rid = route_id or f"{base.map_id}_{start_node}_{end_node}"
    return Route(rid, links)


def route_length(route: Route) -> float:
    total = 0.0
    for link in route.links:
        pts = link.points
        for i in range(len(pts) - 1):
            x0, y0 = pts[i]
            x1, y1 = pts[i + 1]
            total += ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    return total
