# tests/test_control.py
import math
from control.pure_pursuit import PurePursuit
from control.config import LOOKAHEAD_DISTANCE, TARGET_SPEED, SPEED_KP
from simulator.config import MAX_STEER_ANGLE, MAX_ACC, MAX_DECEL
from simulator.world import SimulationWorld
from config import DT


def _state(x=0.0, y=0.0, yaw=0.0, speed=0.0) -> dict:
    return {"x": x, "y": y, "yaw": yaw, "speed": speed}


def test_empty_path_returns_zero():
    """空路径时控制输出为零"""
    ctrl = PurePursuit()
    acc, steer = ctrl.compute(_state(speed=5.0), path=[])
    assert acc == 0.0
    assert steer == 0.0
    print("✅ 空路径测试通过")


def test_find_lookahead_first_far_enough():
    """沿路径弧长前进 ld，段内插值"""
    ctrl = PurePursuit()
    path = [(0.0, 0.0), (5.0, 0.0), (12.0, 0.0), (30.0, 0.0)]
    target = ctrl._find_lookahead_point(0.0, 0.0, path, ld=8.0)
    assert abs(target[0] - 8.0) < 1e-9
    assert abs(target[1]) < 1e-9
    print("✅ 预瞄点选取测试通过")


def test_find_lookahead_skips_passed_points():
    """车已驶过起点时，从投影点向前预瞄，不回头"""
    ctrl = PurePursuit()
    path = [(0.0, 0.0), (50.0, 0.0), (100.0, 0.0)]
    target = ctrl._find_lookahead_point(10.0, 0.0, path, ld=8.0)
    assert abs(target[0] - 18.0) < 1e-9
    assert abs(target[1]) < 1e-9
    print("✅ 跳过身后路点测试通过")


def test_find_lookahead_fallback_to_end():
    """前方没有足够远的路点时取终点"""
    ctrl = PurePursuit()
    path = [(0.0, 0.0), (5.0, 0.0), (10.0, 0.0)]
    target = ctrl._find_lookahead_point(0.0, 0.0, path, ld=20.0)
    assert target == (10.0, 0.0)
    print("✅ 预瞄点终点回退测试通过")


def test_steer_straight_ahead_near_zero():
    """目标点在正前方时转角接近 0"""
    ctrl = PurePursuit(lookahead=8.0)
    acc, steer = ctrl.compute(
        _state(x=0.0, y=0.0, yaw=0.0, speed=5.0),
        path=[(0.0, 0.0), (20.0, 0.0)],
    )
    assert abs(steer) < 1e-6
    print("✅ 直行转角测试通过")


def test_steer_left_positive():
    """目标点在左侧时前轮转角为正（左转）"""
    ctrl = PurePursuit(lookahead=5.0)
    _, steer = ctrl.compute(
        _state(x=0.0, y=0.0, yaw=0.0, speed=5.0),
        path=[(10.0, 5.0)],
    )
    assert steer > 0
    print("✅ 左转方向测试通过")


def test_steer_right_negative():
    """目标点在右侧时前轮转角为负（右转）"""
    ctrl = PurePursuit(lookahead=5.0)
    _, steer = ctrl.compute(
        _state(x=0.0, y=0.0, yaw=0.0, speed=5.0),
        path=[(10.0, -5.0)],
    )
    assert steer < 0
    print("✅ 右转方向测试通过")


def test_longitudinal_p_control():
    """纵向加速度与速度误差成比例"""
    ctrl = PurePursuit(target_speed=TARGET_SPEED, speed_kp=SPEED_KP)
    speed = 6.0
    expected = SPEED_KP * (TARGET_SPEED - speed)
    assert abs(ctrl._calc_acc(speed, TARGET_SPEED) - expected) < 1e-9

    # 高于目标速时应减速
    assert ctrl._calc_acc(12.0, TARGET_SPEED) < 0
    print("✅ 纵向 P 控制测试通过")


def test_target_speed_override():
    """compute 的 target_speed 参数可覆盖默认巡航速度"""
    ctrl = PurePursuit(target_speed=10.0, speed_kp=0.1)
    acc_default, _ = ctrl.compute(_state(speed=0.0), path=[(20.0, 0.0)])
    acc_override, _ = ctrl.compute(
        _state(speed=0.0), path=[(20.0, 0.0)], target_speed=4.0
    )
    assert abs(acc_default - 1.0) < 1e-9   # 0.1 * 10
    assert abs(acc_override - 0.4) < 1e-9  # 0.1 * 4
    assert acc_override < acc_default
    print("✅ 目标车速覆盖测试通过")


def test_steer_and_acc_clamped():
    """转角与加速度输出不超过车辆约束"""
    ctrl = PurePursuit(lookahead=1.0, target_speed=100.0, speed_kp=10.0)
    # 很大横向偏差，迫使转角饱和；很大速度误差迫使加速度饱和
    acc, steer = ctrl.compute(
        _state(x=0.0, y=0.0, yaw=0.0, speed=0.0),
        path=[(1.0, 50.0)],
    )
    assert -MAX_STEER_ANGLE <= steer <= MAX_STEER_ANGLE
    assert MAX_DECEL <= acc <= MAX_ACC
    print("✅ 控制量限幅测试通过")


def test_closed_loop_tracks_straight_path():
    """闭环：沿直线路径行驶一段时间后横向偏差仍较小"""
    world = SimulationWorld()
    world.set_reference_path([(0.0, 0.0), (50.0, 0.0), (100.0, 0.0)])
    ctrl = PurePursuit(lookahead=LOOKAHEAD_DISTANCE, target_speed=8.0)

    # 给一点初始速度，避免静止时几何退化
    world.vehicle.reset(x=0.0, y=0.2, yaw=0.0, speed=5.0)

    for _ in range(int(8.0 / DT)):
        state = world.vehicle.get_state()
        acc, steer = ctrl.compute(state, world.reference_path)
        world.step(acc, steer)

    final = world.vehicle.get_state()
    assert abs(final["y"]) < 0.5
    assert final["x"] > 20.0
    print("✅ 直线路径闭环跟踪测试通过")


if __name__ == "__main__":
    test_empty_path_returns_zero()
    test_find_lookahead_first_far_enough()
    test_find_lookahead_skips_passed_points()
    test_find_lookahead_fallback_to_end()
    test_steer_straight_ahead_near_zero()
    test_steer_left_positive()
    test_steer_right_negative()
    test_longitudinal_p_control()
    test_target_speed_override()
    test_steer_and_acc_clamped()
    test_closed_loop_tracks_straight_path()
    print("\n🎉 控制模块全部测试通过")
