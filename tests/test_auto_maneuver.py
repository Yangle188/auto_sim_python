"""P3a：路口 auto-maneuver。"""
from sim_server.scene_schema import urban_left_scene_config
from sim_server.session import SimSession
from hmi.hmi_manager import CODE_AUTO_MANEUVER


def test_urban_left_auto_maneuver_triggers():
    scene = urban_left_scene_config()
    assert scene.planned_maneuver == "left"
    sess = SimSession(scene)
    sess.start()
    # 待机并激活
    for _ in range(800):
        snap = sess.step_once()
        assert snap is not None
        if snap["state"] == "STANDBY" and snap["vehicle"]["speed"] >= 5.0:
            break
    assert sess.request_activate()["ok"] is True

    saw = False
    for _ in range(2000):
        snap = sess.step_once()
        if snap is None:
            break
        if any(a["code"] == CODE_AUTO_MANEUVER for a in sess.hmi.get_active_alerts()):
            saw = True
        pref = snap.get("prefer_maneuver")
        if pref == "left":
            # 切链后路径应朝北（末端 y 明显大于 0）
            path = snap.get("path") or []
            if path:
                ys = [p[1] for p in path[-5:]]
                assert max(ys) > 5.0
            break
    assert saw, "接近路口应触发 auto-maneuver 日志"
    assert sess.lane_change.prefer_maneuver == "left"
