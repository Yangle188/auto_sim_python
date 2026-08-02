"""ACC 跟车 / cut-in / cut-out 纵向规划单测。"""
from types import SimpleNamespace

from planning.traj_planner import TrajPlanner
from sim_server.scene_schema import (
    acc_scene_config,
    evaluate_motion,
    default_scene_config,
)
from simulator.config import LANE_WIDTH


def _path(length: float = 200.0, step: float = 2.0):
    n = int(length / step) + 1
    return [(i * step, 0.0) for i in range(n)]


def test_follow_matches_slower_lead():
    planner = TrajPlanner()
    path = _path()
    ego = {"x": 10.0, "y": 0.0, "speed": 10.0}
    # 前车在本车道，间距约 20m，车速 6
    pred = SimpleNamespace(
        x=30.0,
        y=0.0,
        vx=6.0,
        vy=0.0,
        coasting=False,
        trajectory=[(30.0, 0.0), (36.0, 0.0), (42.0, 0.0)],
    )
    v = planner.plan(ego, path, predictions=[pred], speed_limit=12.0)
    assert v < 10.0
    # 保险杠净空修正后目标速略低于纯时距匹配
    assert v > 3.0
    assert planner.last_lead is not None
    assert planner.last_lead["source"] == "follow"


def test_cutin_from_adjacent_lane_via_prediction():
    planner = TrajPlanner()
    path = _path()
    ego = {"x": 10.0, "y": 0.0, "speed": 11.0}
    # 当前在左道，预测点进入本车道
    pred = SimpleNamespace(
        x=28.0,
        y=LANE_WIDTH,
        vx=8.0,
        vy=-1.5,
        coasting=False,
        trajectory=[
            (28.0, LANE_WIDTH),
            (30.0, LANE_WIDTH * 0.4),
            (32.0, 0.0),
            (36.0, 0.0),
        ],
    )
    v = planner.plan(ego, path, predictions=[pred], speed_limit=12.0)
    assert planner.last_lead is not None
    assert planner.last_lead["source"] == "cutin"
    assert v < 12.0


def test_cutout_clears_lead_and_returns_to_limit():
    planner = TrajPlanner()
    path = _path()
    ego = {"x": 10.0, "y": 0.0, "speed": 7.0}
    # 前车已在右道，超出横向阈值
    pred = SimpleNamespace(
        x=35.0,
        y=-LANE_WIDTH,
        vx=9.0,
        vy=0.0,
        coasting=False,
        trajectory=[(35.0, -LANE_WIDTH), (44.0, -LANE_WIDTH)],
    )
    v = planner.plan(ego, path, predictions=[pred], speed_limit=12.0)
    assert planner.last_lead is None
    assert v == 12.0


def test_adjacent_lane_not_treated_as_lead():
    planner = TrajPlanner()
    path = _path()
    ego = {"x": 0.0, "y": 0.0, "speed": 10.0}
    pred = SimpleNamespace(
        x=25.0,
        y=LANE_WIDTH,
        vx=6.0,
        vy=0.0,
        coasting=False,
        trajectory=[(25.0, LANE_WIDTH), (31.0, LANE_WIDTH)],
    )
    v = planner.plan(ego, path, predictions=[pred], speed_limit=12.0)
    assert planner.last_lead is None
    assert v == 12.0


def test_acc_scene_scripted_motion_phases():
    cfg = acc_scene_config()
    assert cfg.route_id == "acc_highway"
    motion = cfg.obstacles[0].motion
    assert motion is not None and motion.type == "scripted"

    x0, y0 = evaluate_motion(motion, 0.0)
    assert abs(y0) < 0.1  # 本车道跟车

    _, y_mid = evaluate_motion(motion, 16.0)
    assert y_mid > LANE_WIDTH * 0.5  # cut-out 后在左道

    _, y_in = evaluate_motion(motion, 24.0)
    assert abs(y_in) < 0.5  # cut-in 回本车道

    _, y_out = evaluate_motion(motion, 34.0)
    assert y_out < -LANE_WIDTH * 0.5  # 再 cut-out 到右道


def test_truth_leads_override_noisy_predictions():
    """提供 leads 时，邻道静止预测不应再误触发 ACC。"""
    planner = TrajPlanner()
    path = _path()
    ego = {"x": 10.0, "y": 0.0, "speed": 10.0}
    leads = [{"x": 40.0, "y": -LANE_WIDTH, "vx": 10.0, "vy": 0.0}]
    noisy = SimpleNamespace(
        x=35.0,
        y=-LANE_WIDTH,
        vx=5.0,
        vy=2.0,
        coasting=False,
        trajectory=[(35.0, -LANE_WIDTH), (40.0, 0.0), (45.0, 0.0)],
    )
    v = planner.plan(
        ego, path, predictions=[noisy], speed_limit=12.0, leads=leads
    )
    assert planner.last_lead is None
    assert v == 12.0


def test_default_scene_is_acc_highway():
    cfg = default_scene_config()
    assert cfg.route_id == "acc_highway"
