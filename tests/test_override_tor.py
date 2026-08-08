"""P2：TOR / OVERRIDE 演示入口。"""
from sim_server.scene_schema import RouteLinkIn, SceneConfig
from sim_server.session import SimSession
from hmi.hmi_manager import CODE_OVERRIDE, CODE_TOR


def _run_to_standby_ready(sess: SimSession, max_steps: int = 500):
    for _ in range(max_steps):
        snap = sess.step_once()
        assert snap is not None
        if snap["state"] == "STANDBY" and snap["vehicle"]["speed"] >= 5.0:
            return snap
    raise AssertionError("未能进入可激活 STANDBY")


def _active_session() -> SimSession:
    scene = SceneConfig(
        route_id="tor_demo",
        links=[
            RouteLinkIn(
                link_id="L1",
                points=[(0.0, 0.0), (200.0, 0.0)],
                speed_limit=12.0,
            )
        ],
        obstacles=[],
        duration_s=30.0,
    )
    sess = SimSession(scene)
    sess.start()
    _run_to_standby_ready(sess)
    assert sess.request_activate()["ok"] is True
    assert sess.state_machine.get_state() == "ACTIVE"
    return sess


def test_tor_then_override_and_exit():
    sess = _active_session()
    st = sess.status_payload()
    assert st["can_tor"] is True
    assert st["can_override"] is True
    assert st["tor_pending"] is False

    tor = sess.request_tor()
    assert tor["ok"] is True and tor["pending"] is True
    assert sess.state_machine.get_state() == "ACTIVE"
    assert any(a["code"] == CODE_TOR for a in sess.hmi.get_active_alerts())
    assert sess.status_payload()["tor_pending"] is True

    ov = sess.request_override()
    assert ov["ok"] is True
    assert ov["ad_state"] == "OVERRIDE"
    assert any(a["code"] == CODE_OVERRIDE for a in sess.hmi.get_active_alerts())
    assert sess.status_payload()["tor_pending"] is False
    assert sess.status_payload()["can_deactivate"] is True
    assert sess.status_payload()["can_override"] is False

    # OVERRIDE 下 AD 不输出控制
    snap = sess.step_once()
    assert snap is not None
    assert snap["state"] == "OVERRIDE"
    assert abs(float(snap["accel"])) < 1e-9
    assert abs(float(snap["steer"])) < 1e-9

    de = sess.request_deactivate()
    assert de["ok"] is True
    assert de["ad_state"] == "STANDBY"


def test_override_without_tor():
    sess = _active_session()
    ov = sess.request_override()
    assert ov["ok"] is True
    assert sess.state_machine.get_state() == "OVERRIDE"


def test_tor_rejected_when_not_active():
    scene = SceneConfig(
        route_id="tor_idle",
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
    _run_to_standby_ready(sess)
    assert sess.request_tor()["ok"] is False
    assert sess.request_override()["ok"] is False
