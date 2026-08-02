"""HMI：功能激活 / 退出 / 限速切换文言。"""
from sim_server.scene_schema import ObstacleIn, RouteLinkIn, SceneConfig
from sim_server.session import SimSession
from hmi.hmi_manager import CODE_AD_ACTIVATE, CODE_AD_EXIT, CODE_SPEED_LIMIT


def _run_to_standby_ready(sess: SimSession, max_steps: int = 500):
    for _ in range(max_steps):
        snap = sess.step_once()
        assert snap is not None
        if snap["state"] == "STANDBY" and snap["vehicle"]["speed"] >= 5.0:
            return snap
    raise AssertionError("未能进入可激活 STANDBY")


def test_hmi_activate_and_exit_messages():
    scene = SceneConfig(
        route_id="hmi_ad",
        links=[
            RouteLinkIn(
                link_id="L1",
                points=[(0.0, 0.0), (150.0, 0.0)],
                speed_limit=12.0,
            )
        ],
        obstacles=[],
        duration_s=25.0,
    )
    sess = SimSession(scene)
    sess.start()
    _run_to_standby_ready(sess)
    assert sess.request_activate()["ok"] is True
    codes = [a["code"] for a in sess.hmi.get_active_alerts()]
    assert CODE_AD_ACTIVATE in codes
    assert any(a["msg"] == "功能已激活" for a in sess.hmi.get_active_alerts())
    snap = sess.step_once()
    assert snap is not None
    assert snap["hmi"]["ad_state"] == "ACTIVE"
    assert snap["hmi"]["latest"]["code"] in (CODE_AD_ACTIVATE, CODE_SPEED_LIMIT) or any(
        a["code"] == CODE_AD_ACTIVATE for a in snap["hmi"]["alerts"]
    )

    assert sess.request_deactivate()["ok"] is True
    assert any(a["code"] == CODE_AD_EXIT for a in sess.hmi.get_active_alerts())
    assert any(a["msg"] == "功能已退出" for a in sess.hmi.get_active_alerts())


def test_hmi_speed_limit_change_message():
    scene = SceneConfig(
        route_id="hmi_limit",
        links=[
            RouteLinkIn(
                link_id="A",
                points=[(0.0, 0.0), (40.0, 0.0)],
                speed_limit=10.0,
            ),
            RouteLinkIn(
                link_id="B",
                points=[(40.0, 0.0), (120.0, 0.0)],
                speed_limit=6.0,
            ),
        ],
        obstacles=[],
        duration_s=30.0,
    )
    sess = SimSession(scene)
    sess.start()
    _run_to_standby_ready(sess)
    sess.request_activate()
    saw = False
    for _ in range(800):
        snap = sess.step_once()
        if snap is None:
            break
        if any(a["code"] == CODE_SPEED_LIMIT for a in snap.get("hmi", {}).get("alerts", [])):
            saw = True
            assert any("限速切换" in a["msg"] for a in snap["hmi"]["alerts"])
            break
    assert saw, "行驶过不同限速路段时应出现限速切换提示"
