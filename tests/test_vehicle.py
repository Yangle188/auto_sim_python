# tests/test_vehicle.py
import math
from simulator.vehicle import Vehicle
from simulator.config import MAX_SPEED, MAX_ACC, MAX_STEER_ANGLE
from config import DT


def test_initial_state():
    """测试初始状态"""
    car = Vehicle()
    state = car.get_state()
    assert state["x"] == 0.0
    assert state["y"] == 0.0
    assert state["yaw"] == 0.0
    assert state["speed"] == 0.0
    print("✅ 初始状态测试通过")


def test_straight_acceleration():
    """测试直线加速：转角为0时，仅x方向位移"""
    car = Vehicle()
    acc = 2.0
    step_num = 10
    for _ in range(step_num):
        car.step(acceleration=acc, steer_angle=0.0)

    state = car.get_state()
    t = step_num * DT
    # 理论位移：匀加速公式 0.5 * a * t²
    expected_x = 0.5 * acc * t * t
    expected_speed = acc * t

    assert abs(state["x"] - expected_x) < 1e-3
    assert abs(state["y"]) < 1e-6
    # 浮点数不用==，用近似比较
    assert abs(state["speed"] - expected_speed) < 1e-6
    print("✅ 直线加速测试通过")


def test_steer_yaw_change():
    """测试转向时航向角变化"""
    car = Vehicle()
    car.reset(speed=10.0)  # 初始有速度

    steer = math.radians(10)
    for _ in range(20):
        car.step(acceleration=0, steer_angle=steer)

    state = car.get_state()
    # 转向时yaw应该增大（左转）
    assert state["yaw"] > 0
    print("✅ 转向航向测试通过")


def test_speed_limit():
    """测试车速上限约束"""
    car = Vehicle()
    for _ in range(500):
        car.step(acceleration=MAX_ACC, steer_angle=0)

    assert abs(car.speed - MAX_SPEED) < 1e-6
    print("✅ 车速上限约束测试通过")


def test_steer_limit():
    """测试转角约束"""
    car = Vehicle()
    car.reset(speed=5.0)
    # 输入超过最大转角
    car.step(acceleration=0, steer_angle=math.radians(50))
    state = car.get_state()
    # 最大转角对应的最大yaw变化率
    max_yaw_rate = 5.0 / 2.7 * math.tan(MAX_STEER_ANGLE)
    assert state["yaw"] <= max_yaw_rate * DT + 1e-6
    print("✅ 转角约束测试通过")


if __name__ == "__main__":
    test_initial_state()
    test_straight_acceleration()
    test_steer_yaw_change()
    test_speed_limit()
    test_steer_limit()
    print("\n🎉 车辆模型全部测试通过")