# tests/test_prediction.py
from types import SimpleNamespace

from config import DT
from prediction.predictor import ObstaclePredictor, PredictedObstacle
from prediction.config import PRED_HORIZON, PRED_DT, MAX_COAST_FRAMES
from planning.path_planner import PathPlanner
from planning.traj_planner import TrajPlanner
from planning.config import CRUISE_SPEED


def _det(x: float, y: float):
    return SimpleNamespace(x=x, y=y)


def test_stationary_no_motion_traj():
    """静止检测：速度低于阈值时轨迹仅为当前点"""
    pred = ObstaclePredictor(min_speed_for_motion=0.3)
    pred.step([_det(10.0, 0.0)], DT)
    out = pred.step([_det(10.0, 0.0)], DT)
    assert len(out) == 1
    assert len(out[0].trajectory) == 1
    assert abs(out[0].vx) < 0.3
    print("✅ 静止轨迹测试通过")


def test_constant_velocity_extrapolation():
    """连续同向位移 → 速度与外推点正确"""
    pred = ObstaclePredictor(
        horizon=5,
        pred_dt=0.2,
        vel_lp_alpha=1.0,
        min_speed_for_motion=0.1,
        min_age_for_pred=3,
    )
    pred.step([_det(0.0, 0.0)], DT)
    # 沿 +x 以 2 m/s 运动：每 DT=0.05 位移 0.1
    pred.step([_det(0.1, 0.0)], DT)
    pred.step([_det(0.2, 0.0)], DT)
    out = pred.step([_det(0.3, 0.0)], DT)
    assert len(out) == 1
    p = out[0]
    assert abs(p.vx - 2.0) < 1e-6
    assert abs(p.vy) < 1e-6
    assert len(p.trajectory) == 6  # 当前 + 5
    # k=5 → x = 0.3 + 5*0.2*2 = 2.3
    assert abs(p.trajectory[-1][0] - 2.3) < 1e-6
    assert abs(p.trajectory[-1][1]) < 1e-6
    print("✅ 匀速外推测试通过")


def test_coast_then_delete():
    """丢失检测后 coast，超过上限删除"""
    pred = ObstaclePredictor(max_coast_frames=2, min_speed_for_motion=0.1, vel_lp_alpha=1.0)
    pred.step([_det(0.0, 0.0)], DT)
    pred.step([_det(0.1, 0.0)], DT)
    assert len(pred.get_predictions()) == 1
    # 连续空检测
    pred.step([], DT)
    assert len(pred.get_predictions()) == 1
    assert pred.get_predictions()[0].coasting
    pred.step([], DT)
    assert len(pred.get_predictions()) == 1
    pred.step([], DT)  # coast_frames > 2 → 删除
    assert len(pred.get_predictions()) == 0
    print("✅ 丢失 coast/删除测试通过")


def test_traj_planner_slows_for_prediction():
    """前方预测点挡路时目标车速低于巡航"""
    path = PathPlanner().plan([(0.0, 0.0), (100.0, 0.0)])
    traj = TrajPlanner()
    pred = PredictedObstacle(
        obs_id=1,
        x=20.0,
        y=0.0,
        vx=-2.0,
        vy=0.0,
        trajectory=[(20.0, 0.0), (18.0, 0.0), (16.0, 0.0)],
    )
    v = traj.plan(
        {"x": 0.0, "y": 0.0, "yaw": 0.0, "speed": 8.0},
        path,
        obstacles=[],
        predictions=[pred],
    )
    assert v < CRUISE_SPEED
    print("✅ 预测前瞻减速测试通过")


def test_traj_planner_predictions_optional():
    """不传 predictions 时行为与原先一致（无障碍巡航）"""
    path = PathPlanner().plan([(0.0, 0.0), (100.0, 0.0)])
    traj = TrajPlanner()
    v = traj.plan(
        {"x": 10.0, "y": 0.0, "yaw": 0.0, "speed": 8.0},
        path,
        obstacles=[],
    )
    assert abs(v - CRUISE_SPEED) < 1e-9
    print("✅ predictions 可选兼容测试通过")


def test_default_horizon_config():
    """默认配置下运动障碍轨迹长度正确"""
    pred = ObstaclePredictor(vel_lp_alpha=1.0, min_speed_for_motion=0.1, min_age_for_pred=3)
    pred.step([_det(0.0, 0.0)], DT)
    pred.step([_det(0.2, 0.0)], DT)
    pred.step([_det(0.4, 0.0)], DT)
    out = pred.step([_det(0.6, 0.0)], DT)
    assert len(out[0].trajectory) == PRED_HORIZON + 1
    assert PRED_DT > 0
    assert MAX_COAST_FRAMES >= 1
    print("✅ 默认预测配置测试通过")


if __name__ == "__main__":
    test_stationary_no_motion_traj()
    test_constant_velocity_extrapolation()
    test_coast_then_delete()
    test_traj_planner_slows_for_prediction()
    test_traj_planner_predictions_optional()
    test_default_horizon_config()
    print("\n🎉 预测模块全部测试通过")
