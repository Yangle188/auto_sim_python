# map/demo_base_map.py
"""教学小底图：3×3 路口网格（双向车道中心线）。"""
from __future__ import annotations

from typing import List, Tuple

from .base_map import BaseMap, MapEdge, MapNode

# 网格间距（m）
_S = 40.0


def _bidir(
    a: str,
    b: str,
    ax: float,
    ay: float,
    bx: float,
    by: float,
    speed: float,
    name: str,
    road_class: str = "main",
) -> List[MapEdge]:
    """生成 A↔B 两条有向边（直线中心线）。"""
    pts_ab: Tuple[Tuple[float, float], ...] = ((ax, ay), (bx, by))
    pts_ba: Tuple[Tuple[float, float], ...] = ((bx, by), (ax, ay))
    return [
        MapEdge(
            f"{a}_{b}",
            a,
            b,
            pts_ab,
            speed,
            name=f"{name}→",
            road_class=road_class,
        ),
        MapEdge(
            f"{b}_{a}",
            b,
            a,
            pts_ba,
            speed,
            name=f"{name}←",
            road_class=road_class,
        ),
    ]


def build_campus_grid_map() -> BaseMap:
    """
    3×3 节点网格（原点在左下 N7）:

        N1 ---- N2 ---- N3
         |       |       |
        N4 ---- N5 ---- N6
         |       |       |
        N7 ---- N8 ---- N9

    外圈主路 12 m/s，中间十字辅路感 8 m/s（实为稍慢主路）。
    """
    coords = {
        "N1": (0.0, 2 * _S),
        "N2": (_S, 2 * _S),
        "N3": (2 * _S, 2 * _S),
        "N4": (0.0, _S),
        "N5": (_S, _S),
        "N6": (2 * _S, _S),
        "N7": (0.0, 0.0),
        "N8": (_S, 0.0),
        "N9": (2 * _S, 0.0),
    }
    nodes = [
        MapNode(nid, x, y, name=nid)
        for nid, (x, y) in coords.items()
    ]

    edges: List[MapEdge] = []
    # 水平
    edges += _bidir("N1", "N2", *coords["N1"], *coords["N2"], 12.0, "北横1")
    edges += _bidir("N2", "N3", *coords["N2"], *coords["N3"], 12.0, "北横2")
    edges += _bidir("N4", "N5", *coords["N4"], *coords["N5"], 8.0, "中横1", "aux")
    edges += _bidir("N5", "N6", *coords["N5"], *coords["N6"], 8.0, "中横2", "aux")
    edges += _bidir("N7", "N8", *coords["N7"], *coords["N8"], 12.0, "南横1")
    edges += _bidir("N8", "N9", *coords["N8"], *coords["N9"], 12.0, "南横2")
    # 竖直
    edges += _bidir("N1", "N4", *coords["N1"], *coords["N4"], 12.0, "西纵1")
    edges += _bidir("N4", "N7", *coords["N4"], *coords["N7"], 12.0, "西纵2")
    edges += _bidir("N2", "N5", *coords["N2"], *coords["N5"], 8.0, "中纵1", "aux")
    edges += _bidir("N5", "N8", *coords["N5"], *coords["N8"], 8.0, "中纵2", "aux")
    edges += _bidir("N3", "N6", *coords["N3"], *coords["N6"], 12.0, "东纵1")
    edges += _bidir("N6", "N9", *coords["N6"], *coords["N9"], 12.0, "东纵2")

    return BaseMap(
        map_id="campus_grid",
        title="校园网格（3×3）",
        nodes=nodes,
        edges=edges,
    )


def default_base_map() -> BaseMap:
    return build_campus_grid_map()
