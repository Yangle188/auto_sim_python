# tests/test_map.py
import pytest

from map.link import Link
from map.route import Route
from map.map_manager import MapManager
from map.demo_routes import build_demo_route
from map.config import SPEED_LOOKAHEAD_DIST
from planning.path_planner import PathPlanner
from planning.traj_planner import TrajPlanner


def test_link_rejects_single_point():
    with pytest.raises(ValueError):
        Link("bad", ((0.0, 0.0),), 8.0)


def test_link_rejects_nonpositive_speed():
    with pytest.raises(ValueError):
        Link("bad", ((0.0, 0.0), (1.0, 0.0)), 0.0)


def test_route_rejects_empty_links():
    with pytest.raises(ValueError):
        Route("empty", ())


def test_route_rejects_disconnected_links():
    with pytest.raises(ValueError):
        Route(
            "gap",
            (
                Link("A", ((0.0, 0.0), (10.0, 0.0)), 8.0),
                Link("B", ((20.0, 0.0), (30.0, 0.0)), 6.0),
            ),
        )


def test_set_route_and_waypoints_dedup():
    mgr = MapManager()
    route = build_demo_route()
    mgr.set_route(route)
    wps = mgr.get_waypoints()
    assert wps[0] == (0.0, 0.0)
    assert wps[-1] == (100.0, 2.0)
    # 相邻 link 重复端点应去重
    assert len(wps) == 4  # (0,0),(40,0),(70,1),(100,2)
    for i in range(len(wps) - 1):
        assert wps[i] != wps[i + 1]


def test_speed_limit_by_link_region():
    mgr = MapManager()
    mgr.set_route(build_demo_route())
    assert mgr.get_speed_limit(10.0, 0.0) == pytest.approx(8.0)
    assert mgr.get_speed_limit(55.0, 0.5) == pytest.approx(12.0)
    assert mgr.get_speed_limit(90.0, 1.7) == pytest.approx(6.0)


def test_speed_limit_ahead_approaching_l3():
    mgr = MapManager()
    mgr.set_route(build_demo_route())
    # 距 L3 起点约 15m（弧长），默认前瞻 20m → 应已看到 6
    v = mgr.get_speed_limit_ahead(55.0, 0.5, lookahead=SPEED_LOOKAHEAD_DIST)
    assert v == pytest.approx(6.0)


def test_speed_limit_ahead_on_l1_stays_8():
    mgr = MapManager()
    mgr.set_route(build_demo_route())
    # 前瞻未进入 L3；L2 更高，最低仍为当前 8
    v = mgr.get_speed_limit_ahead(20.0, 0.0, lookahead=20.0)
    assert v == pytest.approx(8.0)


def test_no_route_returns_none():
    mgr = MapManager()
    assert mgr.get_speed_limit(0.0, 0.0) is None
    assert mgr.get_speed_limit_ahead(0.0, 0.0) is None


def test_clear_route():
    mgr = MapManager()
    mgr.set_route(build_demo_route())
    mgr.clear_route()
    assert mgr.get_waypoints() == []
    assert mgr.get_speed_limit(10.0, 0.0) is None


def test_traj_planner_respects_speed_limit():
    path = PathPlanner().plan([(0.0, 0.0), (100.0, 0.0)])
    traj = TrajPlanner()
    v = traj.plan(
        {"x": 10.0, "y": 0.0, "yaw": 0.0, "speed": 5.0},
        path,
        obstacles=[],
        speed_limit=6.0,
    )
    assert abs(v - 6.0) < 1e-9


def test_traj_planner_none_speed_limit_uses_cruise():
    path = PathPlanner().plan([(0.0, 0.0), (100.0, 0.0)])
    traj = TrajPlanner()
    v = traj.plan(
        {"x": 10.0, "y": 0.0, "yaw": 0.0, "speed": 5.0},
        path,
        obstacles=[],
        speed_limit=None,
    )
    assert abs(v - traj.cruise_speed) < 1e-9


def test_get_route_links_for_viz():
    mgr = MapManager()
    mgr.set_route(build_demo_route())
    links = mgr.get_route_links()
    assert len(links) == 3
    assert links[0]["link_id"] == "L1"
    assert links[2]["speed_limit"] == 6.0
