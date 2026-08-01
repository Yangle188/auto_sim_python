# tests/test_localization.py
import math

from config import DT
from localization.ekf_localizer import EKFLocalizer, _normalize_angle
from simulator.config import WHEEL_BASE


def test_get_state_keys():
    """get_state 字段与控制模块兼容"""
    loc = EKFLocalizer()
    loc.reset(x=1.0, y=2.0, yaw=0.3, speed=4.0)
    st = loc.get_state()
    assert set(st.keys()) == {"x", "y", "yaw", "speed"}
    assert abs(st["x"] - 1.0) < 1e-12
    assert abs(st["speed"] - 4.0) < 1e-12
    print("✅ get_state 字段测试通过")


def test_predict_matches_euler_bicycle():
    """无过程噪声时 predict 与欧拉自行车公式一致"""
    loc = EKFLocalizer(process_vars=[0.0, 0.0, 0.0, 0.0])
    loc.reset(x=0.0, y=0.0, yaw=0.0, speed=5.0)
    acc = 1.0
    steer = 0.1
    loc.predict(acc, steer, DT)

    # 手算一帧欧拉
    v = 5.0
    yaw = 0.0
    x = 0.0 + v * math.cos(yaw) * DT
    y = 0.0 + v * math.sin(yaw) * DT
    yaw2 = yaw + (v / WHEEL_BASE) * math.tan(steer) * DT
    v2 = v + acc * DT

    st = loc.get_state()
    assert abs(st["x"] - x) < 1e-9
    assert abs(st["y"] - y) < 1e-9
    assert abs(st["yaw"] - yaw2) < 1e-9
    assert abs(st["speed"] - v2) < 1e-9
    print("✅ predict 欧拉一致性测试通过")


def test_update_gps_reduces_position_error():
    """初值偏置后，多次无噪声 GPS 更新应显著降低位置误差"""
    loc = EKFLocalizer()
    loc.reset(x=5.0, y=-3.0, yaw=0.0, speed=0.0)
    true_xy = (0.0, 0.0)
    err0 = math.hypot(loc.x[0] - true_xy[0], loc.x[1] - true_xy[1])
    for _ in range(20):
        loc.update_gps(true_xy[0], true_xy[1])
    err1 = math.hypot(loc.x[0] - true_xy[0], loc.x[1] - true_xy[1])
    assert err1 < 0.2 * err0
    assert err1 < 0.5
    print("✅ GPS 更新降误差测试通过")


def test_yaw_normalized_after_predict():
    """航向角预测后落在 (-pi, pi]"""
    loc = EKFLocalizer(process_vars=[0.0, 0.0, 0.0, 0.0])
    loc.reset(x=0.0, y=0.0, yaw=math.pi + 0.1, speed=2.0)
    loc.predict(0.0, 0.0, DT)
    yaw = loc.get_state()["yaw"]
    assert -math.pi < yaw <= math.pi
    assert abs(yaw - _normalize_angle(math.pi + 0.1)) < 1e-9
    print("✅ 航向角归一化测试通过")


def test_simulate_gps_noise_reproducible():
    """固定种子下 GPS 噪声可复现且非零"""
    loc1 = EKFLocalizer(rng_seed=42)
    loc2 = EKFLocalizer(rng_seed=42)
    true = {"x": 10.0, "y": -2.0, "yaw": 0.0, "speed": 0.0}
    g1 = loc1.simulate_gps(true)
    g2 = loc2.simulate_gps(true)
    assert g1 == g2
    assert abs(g1[0] - true["x"]) > 1e-6 or abs(g1[1] - true["y"]) > 1e-6
    print("✅ GPS 噪声复现测试通过")


def test_covariance_shape():
    """协方差为 4x4"""
    loc = EKFLocalizer()
    P = loc.get_covariance()
    assert len(P) == 4 and all(len(row) == 4 for row in P)
    loc.predict(0.5, 0.0, DT)
    loc.update_gps(0.0, 0.0)
    P2 = loc.get_covariance()
    assert len(P2) == 4
    print("✅ 协方差维度测试通过")


if __name__ == "__main__":
    test_get_state_keys()
    test_predict_matches_euler_bicycle()
    test_update_gps_reduces_position_error()
    test_yaw_normalized_after_predict()
    test_simulate_gps_noise_reproducible()
    test_covariance_shape()
    print("\n🎉 定位模块全部测试通过")
