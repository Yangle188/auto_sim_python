# map/base_map.py
"""路网底图：节点 + 有向边（车道中心线折线）。"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class MapNode:
    node_id: str
    x: float
    y: float
    name: str = ""


@dataclass(frozen=True)
class MapEdge:
    """有向边：from → to，points 含两端点。"""

    edge_id: str
    from_node: str
    to_node: str
    points: Tuple[Tuple[float, float], ...]
    speed_limit: float
    name: str = ""
    road_class: str = "main"
    maneuver: str = "straight"

    def __post_init__(self) -> None:
        pts = tuple((float(x), float(y)) for x, y in self.points)
        object.__setattr__(self, "points", pts)
        if len(pts) < 2:
            raise ValueError(f"MapEdge {self.edge_id}: need at least 2 points")
        if self.speed_limit <= 0.0:
            raise ValueError(f"MapEdge {self.edge_id}: speed_limit must be > 0")

    @property
    def length(self) -> float:
        total = 0.0
        for i in range(len(self.points) - 1):
            x0, y0 = self.points[i]
            x1, y1 = self.points[i + 1]
            total += math.hypot(x1 - x0, y1 - y0)
        return total


class BaseMap:
    """教学用路网底图。"""

    def __init__(
        self,
        map_id: str,
        nodes: Iterable[MapNode],
        edges: Iterable[MapEdge],
        title: str = "",
    ) -> None:
        self.map_id = map_id
        self.title = title or map_id
        self.nodes: Dict[str, MapNode] = {n.node_id: n for n in nodes}
        self.edges: Dict[str, MapEdge] = {}
        self._out: Dict[str, List[str]] = {nid: [] for nid in self.nodes}
        for e in edges:
            self._add_edge(e)

    def _add_edge(self, edge: MapEdge) -> None:
        if edge.edge_id in self.edges:
            raise ValueError(f"duplicate edge_id {edge.edge_id}")
        if edge.from_node not in self.nodes or edge.to_node not in self.nodes:
            raise ValueError(f"edge {edge.edge_id}: unknown node")
        self.edges[edge.edge_id] = edge
        self._out[edge.from_node].append(edge.edge_id)

    def outgoing(self, node_id: str) -> List[MapEdge]:
        return [self.edges[eid] for eid in self._out.get(node_id, [])]

    def nearest_node(
        self, x: float, y: float, max_dist: float = 25.0
    ) -> Optional[MapNode]:
        best: Optional[MapNode] = None
        best_d = float("inf")
        for n in self.nodes.values():
            d = math.hypot(n.x - x, n.y - y)
            if d < best_d:
                best_d = d
                best = n
        if best is None or best_d > max_dist:
            return None
        return best

    def to_dict(self, *, with_lane_markings: bool = True) -> dict:
        from .road_viz import base_map_lane_markings

        data = {
            "map_id": self.map_id,
            "title": self.title,
            "nodes": [
                {
                    "node_id": n.node_id,
                    "x": n.x,
                    "y": n.y,
                    "name": n.name,
                }
                for n in self.nodes.values()
            ],
            "edges": [
                {
                    "edge_id": e.edge_id,
                    "from_node": e.from_node,
                    "to_node": e.to_node,
                    "points": [[p[0], p[1]] for p in e.points],
                    "speed_limit": e.speed_limit,
                    "name": e.name,
                    "road_class": e.road_class,
                    "maneuver": e.maneuver,
                    "length": e.length,
                }
                for e in self.edges.values()
            ],
        }
        if with_lane_markings:
            data["lane_markings"] = base_map_lane_markings(self)
        return data
