# map/demo_routes.py
"""教学用默认路线：多 link、不同限速。"""
from .link import Link
from .route import Route


def build_demo_route() -> Route:
    """
    L1: (0,0)→(40,0)  @ 8 m/s
    L2: (40,0)→(70,1) @ 12 m/s
    L3: (70,1)→(100,2) @ 6 m/s
    """
    return Route(
        route_id="demo_main",
        links=(
            Link("L1", ((0.0, 0.0), (40.0, 0.0)), 8.0),
            Link("L2", ((40.0, 0.0), (70.0, 1.0)), 12.0),
            Link("L3", ((70.0, 1.0), (100.0, 2.0)), 6.0),
        ),
    )
