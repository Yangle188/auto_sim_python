# tests/test_aeb.py
from types import SimpleNamespace

from safety.aeb import AEBController, MODE_AEB, MODE_FCW, MODE_NONE
from sim_server.scene_schema import highway_aeb_scene_config
from sim_server.session import SimSession
from config import DT, STATE_ACTIVE
from simulator.config import MAX_DECEL


def test_aeb_fcw_then_brake():
    aeb = AEBController()
    path = [(0.0, 0.0), (200.0, 0.0)]
    # 中距：TTC 落在 FCW 窗口，未达 AEB
    r1 = aeb.evaluate(
        {"x": 0.0, "y": 0.0, "speed": 10.0},
        path,
        leads=[{"x": 28.0, "y": 0.0, "vx": 0.0, "vy": 0.0, "height": 4.0}],
    )
    assert r1.mode == MODE_FCW, r1
    # 近距 → AEB
    r2 = aeb.evaluate(
        {"x": 0.0, "y": 0.0, "speed": 12.0},
        path,
        leads=[{"x": 12.0, "y": 0.0, "vx": 0.0, "vy": 0.0, "height": 4.0}],
    )
    assert r2.mode == MODE_AEB
    assert r2.acc is not None and r2.acc <= MAX_DECEL + 1e-6


def test_aeb_accepts_prediction_style_leads():
    """感知预测对象（带 vx/vy）可作为 AEB leads。"""
    aeb = AEBController()
    path = [(0.0, 0.0), (200.0, 0.0)]
    pred = SimpleNamespace(x=12.0, y=0.0, vx=0.0, vy=0.0, height=4.0)
    r = aeb.evaluate(
        {"x": 0.0, "y": 0.0, "speed": 12.0},
        path,
        leads=[pred],
    )
    assert r.mode == MODE_AEB


def test_session_aeb_no_collision():
    sess = SimSession(highway_aeb_scene_config())
    sess.start()
    min_gap = float("inf")
    saw_fcw = False
    saw_aeb = False
    for _ in range(int(22.0 / DT)):
        snap = sess.step_once()
        if snap is None:
            break
        st = sess.state_machine.get_state()
        if st == "STANDBY":
            sess.request_activate()
        if st == STATE_ACTIVE or st == "STANDBY":
            mode = sess.aeb.last.mode
            if mode == MODE_FCW:
                saw_fcw = True
            if mode == MODE_AEB:
                saw_aeb = True
            if sess.aeb.last.d_gap is not None:
                min_gap = min(min_gap, float(sess.aeb.last.d_gap))
        # 几何粗检：自车与障碍中心距离
        ego = snap["vehicle"]
        for obs in snap["obstacles"]:
            dx = float(obs["x"]) - float(ego["x"])
            dy = float(obs["y"]) - float(ego["y"])
            # 后轴到障碍中心；留一点余量不算绝对碰撞盒
            if abs(dy) < 2.0 and dx > 0:
                gap = dx - 3.5  # 粗略车头
                min_gap = min(min_gap, gap)

    assert saw_aeb or saw_fcw, "应触发 FCW 或 AEB"
    assert min_gap > 0.0, f"发生碰撞/重叠 min_gap={min_gap}"


def test_session_aeb_with_perception_leads():
    """关闭真值 leads 后，AEB 走感知路径仍应能触发 FCW/AEB。"""
    scene = highway_aeb_scene_config()
    scene = scene.model_copy(update={"use_truth_leads": False})
    sess = SimSession(scene)
    sess.start()
    assert sess._use_truth_leads is False
    saw = False
    for _ in range(int(22.0 / DT)):
        snap = sess.step_once()
        if snap is None:
            break
        st = sess.state_machine.get_state()
        if st == "STANDBY":
            sess.request_activate()
        mode = sess.aeb.last.mode
        if mode in (MODE_FCW, MODE_AEB):
            saw = True
            break
    assert saw, "感知 leads 模式下应触发 FCW 或 AEB"
