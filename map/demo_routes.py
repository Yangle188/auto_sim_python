# map/demo_routes.py
"""教学用路线：简易直线；城市：左右转 + 主辅路切换。"""
from .link import Link
from .route import Route


def build_demo_route() -> Route:
    """
    简易近直线（单测 / 兼容旧场景）:
    L1 (0,0)→(40,0)@8 → L2→(70,1)@12 → L3→(100,2)@6
    """
    return Route(
        route_id="demo_main",
        links=(
            Link("L1", ((0.0, 0.0), (40.0, 0.0)), 8.0, name="主路段1", road_class="main"),
            Link("L2", ((40.0, 0.0), (70.0, 1.0)), 12.0, name="主路段2", road_class="main"),
            Link("L3", ((70.0, 1.0), (100.0, 2.0)), 6.0, name="主路段3", road_class="main"),
        ),
    )


def build_urban_turn_route() -> Route:
    """
    含左右转与主辅路切换（默认 Web 演示）:

    主路直行 → 右转进辅路 → 辅路直行 → 左转汇入主路 → 主路直行
    """
    return Route(
        route_id="urban_turns",
        links=(
            Link(
                "M1",
                ((0.0, 0.0), (50.0, 0.0)),
                12.0,
                name="主路直行",
                road_class="main",
                maneuver="straight",
            ),
            Link(
                "A_R",
                ((50.0, 0.0), (58.0, -4.0), (62.0, -18.0)),
                7.0,
                name="右转进辅路",
                road_class="aux",
                maneuver="right",
            ),
            Link(
                "A1",
                ((62.0, -18.0), (62.0, -45.0)),
                6.0,
                name="辅路直行",
                road_class="aux",
                maneuver="straight",
            ),
            Link(
                "A_L",
                ((62.0, -45.0), (68.0, -52.0), (90.0, -52.0)),
                7.0,
                name="左转汇入",
                road_class="aux",
                maneuver="left",
            ),
            Link(
                "M2",
                ((90.0, -52.0), (130.0, -52.0)),
                12.0,
                name="主路汇入后直行",
                road_class="main",
                maneuver="merge",
            ),
        ),
    )
