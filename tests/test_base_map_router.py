# tests/test_base_map_router.py
import pytest

from map.demo_base_map import build_campus_grid_map
from map.router import plan_route, route_length
from map.map_manager import MapManager


def test_campus_grid_connectivity():
    m = build_campus_grid_map()
    assert len(m.nodes) == 9
    # 每条无向边拆成双向 → 12 条无向 × 2 = 24
    assert len(m.edges) == 24
    assert m.nearest_node(0.0, 0.0).node_id == "N7"
    assert m.nearest_node(40.0, 40.0).node_id == "N5"


def test_plan_route_n7_to_n3():
    m = build_campus_grid_map()
    route = plan_route(m, start_node="N7", end_node="N3")
    assert route.links
    # 最短应为 4 段（沿南→东→北，或等价长度）
    assert len(route.links) == 4
    assert route.links[0].points[0] == pytest.approx((0.0, 0.0))
    assert route.links[-1].points[-1] == pytest.approx((80.0, 80.0))
    assert route_length(route) == pytest.approx(160.0)


def test_plan_route_snap_xy():
    m = build_campus_grid_map()
    route = plan_route(m, start_xy=(1.0, -1.0), end_xy=(79.0, 81.0))
    assert route.route_id.endswith("N7_N3") or "N7" in route.route_id
    mgr = MapManager()
    mgr.set_route(route)
    wps = mgr.get_waypoints()
    assert wps[0] == pytest.approx((0.0, 0.0))
    assert wps[-1] == pytest.approx((80.0, 80.0))


def test_plan_same_node_raises():
    m = build_campus_grid_map()
    with pytest.raises(ValueError, match="相同"):
        plan_route(m, start_node="N5", end_node="N5")


def test_plan_unreachable_snap():
    m = build_campus_grid_map()
    with pytest.raises(ValueError, match="吸附"):
        plan_route(m, start_xy=(1000.0, 1000.0), end_xy=(0.0, 0.0))


def test_base_map_has_network_lane_markings():
    from map.road_viz import base_map_lane_markings

    m = build_campus_grid_map()
    marks = base_map_lane_markings(m)
    # 12 条无向边 ×（2 外缘 + 若干分隔）> 12
    assert len(marks) >= 24
    data = m.to_dict()
    assert len(data["lane_markings"]) == len(marks)
