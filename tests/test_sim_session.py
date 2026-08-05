# tests/test_sim_session.py
import math

import pytest
from fastapi.testclient import TestClient

from sim_server.scene_schema import (
    SceneConfig,
    acc_scene_config,
    default_scene_config,
    ObstacleIn,
    RouteLinkIn,
    list_presets,
    urban_scene_config,
    urban_turns_scene_config,
)
from sim_server.session import SimSession
from sim_server.app import app
from map.demo_routes import build_urban_turn_route


def test_default_scene_is_highway_lcc():
    cfg = default_scene_config()
    route = cfg.to_route()
    assert route.route_id == "highway_lcc"
    assert cfg.lane_map_id == "highway_3lane"
    assert cfg.start_lane_index == 2
    assert cfg.obstacles


def test_acc_highway_preset_still_available():
    cfg = acc_scene_config()
    assert cfg.route_id == "acc_highway"
    assert cfg.obstacles[0].dynamic
    assert cfg.obstacles[0].motion.type == "scripted"


def test_urban_arterial_and_turns_available():
    urban = urban_scene_config()
    assert urban.route_id == "urban_arterial"
    assert urban.lane_map_id == "urban_arterial"
    turns = urban_turns_scene_config()
    route = turns.to_route()
    assert route.route_id == "urban_turns"
    classes = {lk.road_class for lk in route.links}
    maneuvers = {lk.maneuver for lk in route.links}
    assert "main" in classes and "aux" in classes
    assert "left" in maneuvers and "right" in maneuvers


def test_urban_route_connectivity():
    route = build_urban_turn_route()
    assert route.links[0].name == "主路直行"
    assert route.links[1].maneuver == "right"
    assert route.links[3].maneuver == "left"


def test_scene_rejects_bad_link():
    with pytest.raises(Exception):
        SceneConfig(
            links=[RouteLinkIn(link_id="L", points=[(0.0, 0.0)], speed_limit=8.0)]
        )


def test_session_step_json_snapshot():
    sess = SimSession(default_scene_config())
    assert sess.status == "idle"
    assert sess.step_once() is None
    sess.start()
    snap = sess.step_once()
    assert snap is not None
    assert isinstance(snap["vehicle"], dict)
    assert isinstance(snap["obstacles"][0], dict)
    assert "x" in snap["obstacles"][0]
    assert isinstance(snap["path"], list)
    assert snap["route_links"]
    assert snap["route_links"][0].get("name")
    assert snap["route_links"][0].get("road_class") in ("main", "aux")
    sess.pause()
    assert sess.step_once() is None
    sess.resume()
    assert sess.step_once() is not None


def test_session_reset_applies_draft():
    sess = SimSession(default_scene_config())
    draft = urban_turns_scene_config()
    draft.links[0].speed_limit = 5.0
    sess.set_draft(draft)
    sess.reset()
    assert sess.applied_config.links[0].speed_limit == 5.0
    assert sess.map_mgr.get_speed_limit(10.0, 0.0) == pytest.approx(5.0)


def test_api_scene_and_control():
    client = TestClient(app)
    r = client.get("/api/scene")
    assert r.status_code == 200
    body = r.json()
    assert "draft" in body
    assert body["draft"]["route_id"] == "highway_lcc"

    r = client.get("/api/presets")
    assert r.status_code == 200
    presets = r.json()
    assert "highway_lcc" in presets["scenes"]
    assert "highway_aeb" in presets["scenes"]
    assert "acc_highway" in presets["scenes"]
    assert "urban_arterial" in presets["scenes"]
    assert "urban_turns" in presets["scenes"]
    assert "simple" in presets["scenes"]

    bad = default_scene_config().model_dump()
    bad["links"][1]["points"] = [[99.0, 99.0], [120.0, 99.0]]
    r = client.put("/api/scene", json=bad)
    assert r.status_code == 400

    good = default_scene_config().model_dump()
    r = client.put("/api/scene", json=good)
    assert r.status_code == 200

    r = client.post("/api/control", json={"action": "reset"})
    assert r.status_code == 200
    r = client.post("/api/control", json={"action": "start"})
    assert r.status_code == 200
    assert r.json()["status"]["status"] == "running"
    r = client.post("/api/control", json={"action": "pause"})
    assert r.json()["status"]["status"] == "paused"


def test_list_presets():
    p = list_presets()
    assert "acc_highway" in p
    assert "urban_turns" in p
    assert "Cut-in" in p["acc_highway"]["title"] or "跟车" in p["acc_highway"]["title"]
    assert "左右转" in p["urban_turns"]["title"] or "主辅" in p["urban_turns"]["title"]


def test_session_snapshot_has_multilane_and_heading_up():
    sess = SimSession(acc_scene_config())
    sess.start()
    snap = sess.step_once()
    assert snap is not None
    assert snap.get("num_lanes") == 3
    assert snap.get("lane_markings")
    assert snap.get("view", {}).get("mode") == "heading_up"
    # highway_3lane：世界系标线；旧 path 居中模式才有 lane_left ≈ ±4.8
    if snap.get("use_world_lanes"):
        assert snap.get("ego_lane_id")
        assert any(m.get("role") == "ego_lane_center" for m in snap["lane_markings"])
    else:
        assert abs(snap["lane_left"][0][1] - 4.8) < 0.2


def test_dynamic_obstacle_requires_motion():
    with pytest.raises(Exception):
        ObstacleIn(x=0, y=0, dynamic=True, motion=None)


def test_session_spawns_along_route_heading():
    """导航竖向路段时自车初始航向应沿首段，避免切角冲出车道。"""
    scene = SceneConfig(
        route_id="campus_grid_N7_N1",
        base_map_id="campus_grid",
        links=[
            RouteLinkIn(
                link_id="N7_N4",
                points=[(0.0, 0.0), (0.0, 40.0)],
                speed_limit=12.0,
            ),
            RouteLinkIn(
                link_id="N4_N1",
                points=[(0.0, 40.0), (0.0, 80.0)],
                speed_limit=12.0,
            ),
        ],
        obstacles=[],
        duration_s=20.0,
    )
    sess = SimSession(scene)
    st = sess.world.vehicle.get_state()
    assert st["x"] == pytest.approx(0.0)
    assert st["y"] == pytest.approx(0.0)
    assert st["yaw"] == pytest.approx(math.pi / 2, abs=1e-3)
    assert sess._network_lane_markings


def test_session_seek_frame_and_preview_in_snapshot():
    scene = SceneConfig(
        route_id="seek_preview",
        links=[
            RouteLinkIn(
                link_id="L1",
                points=[(0.0, 0.0), (80.0, 0.0)],
                speed_limit=10.0,
            )
        ],
        obstacles=[],
        duration_s=12.0,
    )
    sess = SimSession(scene)
    sess.start()
    for _ in range(15):
        snap = sess.step_once()
        assert snap is not None
    assert snap.get("preview_traj")
    assert snap.get("lookahead_path")
    mid = sess.seek_frame(5)
    assert mid is not None
    assert sess.status == "paused"
    assert sess.status_payload()["frame_i"] == 5
    assert sess.status_payload()["scrubbing"] is True
    st = sess.status_payload()
    assert st["frame_total"] >= st["frame_n"]
    assert st["frame_i"] < st["frame_total"] - 1  # 中途时进度条不应贴末端


def test_session_step_prev_next_frames():
    """暂停后可上一帧回看、下一帧单步推进。"""
    scene = SceneConfig(
        route_id="step_frames",
        links=[
            RouteLinkIn(
                link_id="L1",
                points=[(0.0, 0.0), (80.0, 0.0)],
                speed_limit=10.0,
            )
        ],
        obstacles=[],
        duration_s=15.0,
    )
    sess = SimSession(scene)
    sess.start()
    for _ in range(10):
        assert sess.step_once() is not None
    assert sess.status_payload()["frame_n"] == 10
    sess.pause()
    t_tip = sess.current_snapshot()["t"]
    prev = sess.step_frame(-1)
    assert prev is not None
    assert prev["t"] < t_tip
    assert sess.status_payload()["scrubbing"] is True
    nxt = sess.step_frame(+1)
    assert nxt is not None
    assert nxt["t"] == pytest.approx(t_tip)
    # 在最新帧再下一步：推进仿真且保持 paused
    advanced = sess.step_frame(+1)
    assert advanced is not None
    assert advanced["t"] > t_tip
    assert sess.status == "paused"
    assert sess.status_payload()["frame_n"] == 11


def test_session_manual_activate_required():
    """STANDBY→ACTIVE 不再自动，需 request_activate。"""
    scene = SceneConfig(
        route_id="manual_activate",
        links=[
            RouteLinkIn(
                link_id="L1",
                points=[(0.0, 0.0), (120.0, 0.0)],
                speed_limit=12.0,
            )
        ],
        obstacles=[],
        duration_s=20.0,
    )
    sess = SimSession(scene)
    sess.start()
    reached_standby_fast = False
    for _ in range(400):
        snap = sess.step_once()
        assert snap is not None
        assert snap["state"] != "ACTIVE"
        if snap["state"] == "STANDBY" and snap["vehicle"]["speed"] >= 5.0:
            reached_standby_fast = True
            break
    assert reached_standby_fast
    assert sess.status_payload()["can_activate"] is True
    res = sess.request_activate()
    assert res["ok"] is True
    assert sess.state_machine.get_state() == "ACTIVE"
    snap = sess.step_once()
    assert snap is not None
    assert snap["state"] == "ACTIVE"


def test_session_stays_active_while_braking_for_obstacle():
    """跟车/静态刹停导致车速 <5m/s 时不应掉回 STANDBY。"""
    scene = SceneConfig(
        route_id="brake_keep_active",
        links=[
            RouteLinkIn(
                link_id="L1",
                points=[(0.0, 0.0), (120.0, 0.0)],
                speed_limit=12.0,
            )
        ],
        # 障碍放远些，先加速再手动激活，再制动
        obstacles=[ObstacleIn(x=70.0, y=0.0, width=2.0, height=2.0)],
        duration_s=35.0,
    )
    sess = SimSession(scene)
    sess.start()
    saw_active = False
    stayed_active_while_slow = False
    for _ in range(1200):
        snap = sess.step_once()
        if snap is None:
            break
        if (
            snap["state"] == "STANDBY"
            and snap["vehicle"]["speed"] >= 5.0
            and not saw_active
        ):
            assert sess.request_activate()["ok"] is True
        if snap["state"] == "ACTIVE":
            saw_active = True
            if snap["vehicle"]["speed"] < 4.0 and snap["v_cmd"] < 4.0:
                stayed_active_while_slow = True
                break
        if snap["state"] == "STANDBY" and saw_active and snap["vehicle"]["x"] > 20.0:
            if snap["v_cmd"] < 4.0:
                pytest.fail("ACC/静态制动时不应因低速掉回 STANDBY")
    assert saw_active
    assert stayed_active_while_slow


def test_session_brakes_for_static_obstacle_on_path():
    """画布静态障碍应作为真值 lead(v=0) 触发减速，而非直接撞上。"""
    scene = SceneConfig(
        route_id="brake_static",
        links=[
            RouteLinkIn(
                link_id="L1",
                points=[(0.0, 0.0), (100.0, 0.0)],
                speed_limit=10.0,
            )
        ],
        obstacles=[ObstacleIn(x=30.0, y=0.0, width=2.0, height=2.0)],
        duration_s=25.0,
    )
    sess = SimSession(scene)
    sess.start()
    saw_slow = False
    for _ in range(400):
        snap = sess.step_once()
        if snap is None:
            break
        if snap["vehicle"]["x"] > 8.0 and snap["v_cmd"] < 4.0:
            saw_slow = True
            break
        # 不应冲过障碍中心仍高速
        if snap["vehicle"]["x"] > 28.0 and snap["vehicle"]["speed"] > 6.0:
            pytest.fail("未制动：已接近静态障碍仍保持高速")
    assert saw_slow, "接近路径上静态障碍时应降低 v_cmd"


def test_api_basemap_and_route_plan():
    client = TestClient(app)
    r = client.get("/api/basemap")
    assert r.status_code == 200
    bm = r.json()
    assert bm["map_id"] == "campus_grid"
    assert len(bm["nodes"]) == 9
    assert len(bm["edges"]) == 24

    r = client.post(
        "/api/route/plan",
        json={"start_node": "N7", "end_node": "N3", "duration_s": 25.0},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["length_m"] == pytest.approx(160.0)
    assert body["draft"]["route_id"].endswith("N7_N3")
    assert len(body["draft"]["links"]) == 4
    assert body["draft"]["base_map_id"] == "campus_grid"
    assert bm.get("lane_markings")

    r = client.get("/api/scene")
    assert r.json()["draft"]["route_id"] == body["draft"]["route_id"]

    from sim_server.session import SimSession
    from sim_server.scene_schema import SceneConfig

    sess = SimSession(SceneConfig.model_validate(body["draft"]))
    sess.start()
    snap = sess.step_once()
    assert snap is not None
    assert snap.get("network_lane_markings")
    assert len(snap["network_lane_markings"]) >= 24

    r = client.post(
        "/api/route/plan",
        json={"start_node": "N5", "end_node": "N5"},
    )
    assert r.status_code == 400
