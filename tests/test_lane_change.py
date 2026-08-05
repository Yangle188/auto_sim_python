# tests/test_lane_change.py
from map.demo_lane_maps import build_highway_3lane_map
from planning.lane_change import LaneChangeController, LC_CHANGING, LC_IDLE
from sim_server.scene_schema import highway_lcc_scene_config
from sim_server.session import SimSession
from config import STATE_ACTIVE, DT


def test_lane_change_rejects_solid():
    lm = build_highway_3lane_map()
    # 实线段中道
    ctl = LaneChangeController(lm)
    ctl.reset("HW_S1_L1")
    res = ctl.request(
        "left",
        speed=10.0,
        ego_xy=(200.0, 0.0),
        leads=[],
        active=True,
    )
    assert not res.ok
    assert res.reason == "solid"


def test_lane_change_accepts_dashed_and_completes():
    lm = build_highway_3lane_map()
    ctl = LaneChangeController(lm)
    ctl.reset("HW_S0_L2")  # 右道
    res = ctl.request(
        "left",
        speed=10.0,
        ego_xy=(40.0, -3.2),
        leads=[],
        active=True,
    )
    assert res.ok, res.msg
    assert ctl.state == LC_CHANGING
    assert res.path and len(res.path) > 5

    # 模拟已贴近目标车道中心
    done = False
    for _ in range(200):
        tick = ctl.tick(0.05, (40.0 + _ * 0.4, 0.0), leads=[])
        if tick.reason == "completed":
            done = True
            break
    assert done
    assert ctl.ego_lane_id.startswith("HW_")
    assert ctl.ego_lane_id.endswith("_L1") or "L1" in ctl.ego_lane_id
    assert ctl.state == LC_IDLE


def test_session_lane_change_api():
    from framework.state_machine import EV_POWER_ON, EV_SELF_CHECK_OK, EV_ACTIVATE

    sess = SimSession(highway_lcc_scene_config())
    sess.start()
    # 直达 ACTIVE，避免右道静止障导致无法达速
    sess.state_machine.transit(EV_POWER_ON, 0.0)
    sess.state_machine.transit(EV_SELF_CHECK_OK, 0.0)
    sess.world.vehicle.reset(
        x=float(sess.world.vehicle.x),
        y=float(sess.world.vehicle.y),
        yaw=float(sess.world.vehicle.yaw),
        speed=10.0,
    )
    sess.localizer.reset(
        x=float(sess.world.vehicle.x),
        y=float(sess.world.vehicle.y),
        yaw=float(sess.world.vehicle.yaw),
        speed=10.0,
    )
    ok = sess.state_machine.transit(EV_ACTIVATE, 10.0)
    assert ok
    assert sess.state_machine.get_state() == STATE_ACTIVE
    before = sess.lane_change.ego_lane_id
    out = sess.request_lane_change("left")
    assert out["ok"] is True, out
    assert sess.lane_change.state == LC_CHANGING
    for _ in range(int(6.0 / DT)):
        sess.step_once()
    snap = sess.current_snapshot()
    assert snap is not None
    assert "lane_change" in snap
    assert snap.get("ego_lane_id")
    assert before.endswith("_L2")
