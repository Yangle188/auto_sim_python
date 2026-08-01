# tests/test_sim_session.py
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
)
from sim_server.session import SimSession
from sim_server.app import app
from map.demo_routes import build_urban_turn_route


def test_default_scene_is_acc_highway():
    cfg = default_scene_config()
    route = cfg.to_route()
    assert route.route_id == "acc_highway"
    assert len(route.links) >= 2
    assert cfg.obstacles
    assert cfg.obstacles[0].dynamic
    assert cfg.obstacles[0].motion is not None
    assert cfg.obstacles[0].motion.type == "scripted"


def test_urban_scene_still_available():
    cfg = urban_scene_config()
    route = cfg.to_route()
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
    draft = urban_scene_config()
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
    assert body["draft"]["route_id"] == "acc_highway"

    r = client.get("/api/presets")
    assert r.status_code == 200
    presets = r.json()
    assert "acc_highway" in presets["scenes"]
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
    # 最外侧边界约为 ±1.5 * 3.2
    assert abs(snap["lane_left"][0][1] - 4.8) < 0.2


def test_dynamic_obstacle_requires_motion():
    with pytest.raises(Exception):
        ObstacleIn(x=0, y=0, dynamic=True, motion=None)
