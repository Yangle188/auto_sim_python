"""P5/P6：绕障 nudge + DMS 脱手计时 + 仲裁/可配置阈值。"""
from planning.nudge import NudgeController, NUDGE_ACTIVE, NUDGE_IDLE
from map.demo_lane_maps import build_highway_3lane_map
from safety.dms import HandsOffMonitor
from planning.config import HANDS_OFF_TOR_S, HANDS_OFF_WARN_S
from sim_server.scene_schema import nudge_scene_config
from sim_server.session import SimSession
from hmi.hmi_manager import CODE_HANDS_OFF, CODE_NUDGE
from config import DT


def test_nudge_path_bows_laterally():
    lm = build_highway_3lane_map()
    ctrl = NudgeController(enabled=True)
    lcc = lm.chain_centerline(lm.follow_lane_chain("HW_S0_L1"))
    leads = [{"x": 50.0, "y": 0.0, "vx": 0.0, "vy": 0.0, "height": 4.0, "width": 2.0}]
    ev = ctrl.tick(
        active=True,
        lc_idle=True,
        ego_xy=(15.0, 0.0),
        lcc_path=lcc,
        leads=leads,
        lane_map=lm,
        ego_lane_id="HW_S0_L1",
    )
    assert ev and ev.startswith("start:")
    assert ctrl.state == NUDGE_ACTIVE
    path = ctrl.current_path()
    assert path is not None and len(path) >= 4
    ys = [p[1] for p in path]
    assert max(abs(y) for y in ys) > 1.0


def test_nudge_session_triggers():
    sess = SimSession(nudge_scene_config())
    sess.start()
    for _ in range(800):
        snap = sess.step_once()
        assert snap is not None
        if snap["state"] == "STANDBY" and snap["vehicle"]["speed"] >= 5.0:
            break
    assert sess.request_activate()["ok"] is True
    saw = False
    for _ in range(1500):
        snap = sess.step_once()
        if snap is None:
            break
        if any(a["code"] == CODE_NUDGE for a in sess.hmi.get_active_alerts()):
            saw = True
        if snap.get("nudge", {}).get("state") == NUDGE_ACTIVE:
            path = snap.get("path") or []
            if path:
                assert max(abs(p[1]) for p in path) > 0.8
            break
    assert saw, "应触发绕障 nudge 日志"


def _activate_until_nudging(sess: SimSession):
    for _ in range(800):
        snap = sess.step_once()
        assert snap is not None
        if snap["state"] == "STANDBY" and snap["vehicle"]["speed"] >= 5.0:
            break
    assert sess.request_activate()["ok"] is True
    for _ in range(1500):
        snap = sess.step_once()
        if snap is None:
            break
        if snap.get("nudge", {}).get("state") == NUDGE_ACTIVE:
            return snap
    raise AssertionError("未进入 nudging")


def test_nudge_opposite_stalk_rejected():
    sess = SimSession(nudge_scene_config())
    sess.start()
    _activate_until_nudging(sess)
    side = sess.nudge.side
    assert side in ("left", "right")
    opposite = "right" if side == "left" else "left"
    r = sess.request_lane_change(opposite)
    assert r["ok"] is False
    assert r["reason"] == "nudge_conflict"
    assert sess.nudge.state == NUDGE_ACTIVE


def test_nudge_same_side_stalk_preempts():
    sess = SimSession(nudge_scene_config())
    sess.start()
    _activate_until_nudging(sess)
    side = sess.nudge.side
    r = sess.request_lane_change(side)
    assert r["ok"] is True, r
    # 下一帧路径仲裁应中断 nudge
    snap = sess.step_once()
    assert snap is not None
    assert sess.nudge.state == NUDGE_IDLE
    msgs = [a.get("msg", "") for a in sess.hmi.get_active_alerts()]
    assert any("中断绕障" in m for m in msgs)


def test_hands_off_warn_and_tor():
    mon = HandsOffMonitor()
    assert mon.tick(DT, active=False) is None
    ev = None
    t = 0.0
    while t < HANDS_OFF_WARN_S + 0.5:
        ev = mon.tick(DT, active=True)
        t += DT
        if ev == "warn":
            break
    assert ev == "warn"
    while t < HANDS_OFF_TOR_S + 0.5:
        ev = mon.tick(DT, active=True)
        t += DT
        if ev == "tor":
            break
    assert ev == "tor"
    mon.hands_on()
    assert mon.elapsed_s == 0.0
    assert mon.warned is False


def test_hands_off_custom_thresholds():
    mon = HandsOffMonitor(warn_s=2.0, tor_s=4.0)
    payload = mon.status_payload()
    assert payload["hands_off_warn_s"] == 2.0
    assert payload["hands_off_tor_s"] == 4.0
    t = 0.0
    ev = None
    while t < 2.5:
        ev = mon.tick(DT, active=True)
        t += DT
        if ev == "warn":
            break
    assert ev == "warn"
    assert abs(mon.elapsed_s - 2.0) < DT + 1e-6
    while t < 4.5:
        ev = mon.tick(DT, active=True)
        t += DT
        if ev == "tor":
            break
    assert ev == "tor"


def test_session_hands_on_clears_timer():
    from sim_server.scene_schema import RouteLinkIn, SceneConfig

    scene = SceneConfig(
        route_id="dms",
        links=[
            RouteLinkIn(
                link_id="L1", points=[(0.0, 0.0), (150.0, 0.0)], speed_limit=10.0
            )
        ],
        obstacles=[],
        duration_s=30.0,
        nudge_enabled=False,
        hands_off_warn_s=2.0,
        hands_off_tor_s=4.0,
    )
    sess = SimSession(scene)
    sess.start()
    assert sess.dms.warn_s == 2.0
    assert sess.dms.tor_s == 4.0
    for _ in range(800):
        snap = sess.step_once()
        if snap and snap["state"] == "STANDBY" and snap["vehicle"]["speed"] >= 5.0:
            break
    assert sess.request_activate()["ok"] is True
    steps = int(2.0 / DT) + 5
    for _ in range(steps):
        sess.step_once()
    assert any(a["code"] == CODE_HANDS_OFF for a in sess.hmi.get_active_alerts())
    assert sess.request_hands_on()["ok"] is True
    assert sess.dms.elapsed_s == 0.0
    r = sess.set_teaching_flags(hands_off_warn_s=1.0, hands_off_tor_s=3.0)
    assert r["ok"] is True
    assert sess.dms.warn_s == 1.0
    assert sess.dms.tor_s == 3.0
