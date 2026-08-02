"""Pure Pursuit：预瞄插值与直线跟踪稳定性。"""
import math

from control.pure_pursuit import PurePursuit
from simulator.vehicle import Vehicle


def test_preview_trajectory_has_path_and_arc():
    from control.pure_pursuit import PurePursuit

    pp = PurePursuit()
    path = [(0.0, 0.0), (20.0, 0.0), (40.0, 10.0)]
    prev = pp.get_preview_trajectory(
        {"x": 2.0, "y": 0.0, "yaw": 0.0, "speed": 8.0}, path
    )
    assert prev["lookahead"] is not None
    assert len(prev["path_preview"]) >= 2
    assert len(prev["arc_preview"]) >= 2
    assert prev["ld"] >= 6.0


def test_lookahead_interpolates_between_waypoints():
    pp = PurePursuit()
    # 点间距 2m，预瞄 8m → 应落在第 4 段内，而非仅落在离散点上
    path = [(float(i), 0.0) for i in range(0, 41, 2)]
    pt = pp.get_lookahead_point({"x": 0.0, "y": 0.0, "speed": 8.0}, path)
    assert pt is not None
    assert abs(pt[1]) < 1e-9
    # Ld ≈ clip(1.35*8, 6, 16)=10.8
    assert 10.0 < pt[0] < 12.0


def test_straight_tracking_low_weave():
    """闭环直线跟踪：横向峰峰值应明显小于旧版画龙水平。"""
    pp = PurePursuit()
    veh = Vehicle()
    path = [(float(i), 0.0) for i in range(0, 201, 2)]
    ys = []
    for _ in range(400):
        st = veh.get_state()
        if st["x"] > 120:
            break
        acc, steer = pp.compute(st, path, target_speed=10.0)
        veh.step(acc, steer)
        if st["x"] > 20:
            ys.append(veh.y)
    assert ys
    p2p = max(ys) - min(ys)
    assert p2p < 0.25, f"lateral weave too large: {p2p:.3f}m"


def test_steer_sign_left_target():
    pp = PurePursuit()
    # 预瞄点落在左偏路径上
    path = [(0.0, 0.0), (5.0, 0.5), (10.0, 1.5), (20.0, 3.0)]
    # 车在原点朝 +x，目标偏左 → 左转（+y 为左，正转角）
    _, steer = pp.compute(
        {"x": 0.0, "y": 0.0, "yaw": 0.0, "speed": 5.0}, path, target_speed=5.0
    )
    assert steer > 0.0
