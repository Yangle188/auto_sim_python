# tests/test_planning.py
from types import SimpleNamespace

from planning.path_planner import PathPlanner
from planning.traj_planner import TrajPlanner
from planning.config import (
    PATH_RESOLUTION,
    CRUISE_SPEED,
    STOP_DISTANCE,
    SLOW_DISTANCE,
    END_SLOW_DISTANCE,
)


def _state(x=0.0, y=0.0, yaw=0.0, speed=0.0) -> dict:
    return {"x": x, "y": y, "yaw": yaw, "speed": speed}


def _obs(x: float, y: float):
    return SimpleNamespace(x=x, y=y)


def test_path_empty_and_single():
    """空路径 / 单点原样返回"""
    planner = PathPlanner()
    assert planner.plan([]) == []
    assert planner.plan([(1.0, 2.0)]) == [(1.0, 2.0)]
    print("✅ 空/单点路径测试通过")


def test_path_densify_keeps_endpoints():
    """密化后点数增多，首尾坐标不变"""
    planner = PathPlanner(resolution=PATH_RESOLUTION)
    waypoints = [(0.0, 0.0), (50.0, 0.0), (100.0, 2.0)]
    dense = planner.plan(waypoints)
    assert len(dense) > len(waypoints)
    assert dense[0] == (0.0, 0.0)
    assert abs(dense[-1][0] - 100.0) < 1e-9
    assert abs(dense[-1][1] - 2.0) < 1e-9
    # 相邻点弧长不应显著大于 resolution（终点衔接除外）
    import math
    for i in range(len(dense) - 1):
        d = math.hypot(dense[i + 1][0] - dense[i][0], dense[i + 1][1] - dense[i][1])
        assert d <= PATH_RESOLUTION + 1e-6
    print("✅ 路径密化测试通过")


def test_traj_cruise_no_obstacle():
    """无障碍且远离终点时接近巡航速度"""
    path = PathPlanner().plan([(0.0, 0.0), (100.0, 0.0)])
    traj = TrajPlanner()
    v = traj.plan(_state(x=10.0, y=0.0), path, obstacles=[])
    assert abs(v - CRUISE_SPEED) < 1e-9
    print("✅ 无障碍巡航测试通过")


def test_traj_slow_near_obstacle():
    """正前方路径上障碍应显著降速"""
    path = PathPlanner().plan([(0.0, 0.0), (100.0, 0.0)])
    traj = TrajPlanner()
    # 障碍在 x=20，车在原点 → 距离约 20，处于 (STOP, SLOW) 减速区
    v = traj.plan(_state(x=0.0, y=0.0), path, obstacles=[_obs(20.0, 0.0)])
    assert v < CRUISE_SPEED
    assert v > 0.0
    print("✅ 障碍减速测试通过")


def test_traj_stop_very_near_obstacle():
    """障碍纵向距离 <= STOP_DISTANCE 时目标车速为 0"""
    path = PathPlanner().plan([(0.0, 0.0), (100.0, 0.0)])
    traj = TrajPlanner()
    v = traj.plan(
        _state(x=0.0, y=0.0),
        path,
        obstacles=[_obs(STOP_DISTANCE, 0.0)],
    )
    assert v == 0.0
    print("✅ 障碍停车测试通过")


def test_traj_ignore_lateral_obstacle():
    """横向超出 clearance 的障碍不触发减速"""
    path = PathPlanner().plan([(0.0, 0.0), (100.0, 0.0)])
    traj = TrajPlanner()
    v = traj.plan(_state(x=0.0, y=0.0), path, obstacles=[_obs(20.0, 10.0)])
    assert abs(v - CRUISE_SPEED) < 1e-9
    print("✅ 旁侧障碍忽略测试通过")


def test_traj_slow_near_end():
    """接近路径终点时应减速"""
    path = PathPlanner().plan([(0.0, 0.0), (100.0, 0.0)])
    traj = TrajPlanner()
    # 车距终点约 END_SLOW_DISTANCE / 2
    x = 100.0 - 0.5 * END_SLOW_DISTANCE
    v = traj.plan(_state(x=x, y=0.0), path, obstacles=[])
    assert v < CRUISE_SPEED
    assert v > 0.0
    print("✅ 终点减速测试通过")


def test_traj_past_end_zero_speed():
    """已越过路径终点时目标车速为 0"""
    path = PathPlanner().plan([(0.0, 0.0), (100.0, 0.0)])
    traj = TrajPlanner()
    v = traj.plan(_state(x=110.0, y=0.0), path, obstacles=[])
    assert v == 0.0
    print("✅ 越过终点停车测试通过")


def test_traj_short_path_returns_zero():
    """路径点不足时目标车速为 0"""
    traj = TrajPlanner()
    assert traj.plan(_state(), path=[], obstacles=[]) == 0.0
    assert traj.plan(_state(), path=[(0.0, 0.0)], obstacles=[]) == 0.0
    print("✅ 短路径回退测试通过")


def test_traj_obstacle_closer_slower():
    """更近的挡路障碍对应更低目标车速"""
    path = PathPlanner().plan([(0.0, 0.0), (100.0, 0.0)])
    traj = TrajPlanner()
    mid = 0.5 * (STOP_DISTANCE + SLOW_DISTANCE)
    near = STOP_DISTANCE + 2.0
    v_far = traj.plan(_state(x=0.0, y=0.0), path, obstacles=[_obs(mid, 0.0)])
    v_near = traj.plan(_state(x=0.0, y=0.0), path, obstacles=[_obs(near, 0.0)])
    assert v_near < v_far
    print("✅ 障碍距离-速度单调测试通过")


if __name__ == "__main__":
    test_path_empty_and_single()
    test_path_densify_keeps_endpoints()
    test_traj_cruise_no_obstacle()
    test_traj_slow_near_obstacle()
    test_traj_stop_very_near_obstacle()
    test_traj_ignore_lateral_obstacle()
    test_traj_slow_near_end()
    test_traj_past_end_zero_speed()
    test_traj_short_path_returns_zero()
    test_traj_obstacle_closer_slower()
    print("\n🎉 规划模块全部测试通过")
