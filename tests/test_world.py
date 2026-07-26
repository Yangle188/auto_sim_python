# tests/test_world.py
from simulator.world import SimulationWorld


def test_world_init():
    """测试世界初始化状态"""
    world = SimulationWorld()
    state = world.get_state()
    assert state["vehicle"]["speed"] == 0.0
    assert state["vehicle"]["x"] == 0.0
    assert state["obstacle_count"] == 0
    assert state["path_point_num"] == 0
    print("✅ 世界初始化测试通过")


def test_add_obstacle_and_path():
    """测试添加障碍物与参考路径"""
    world = SimulationWorld()
    world.add_obstacle(10.0, 0.0, 2.0, 2.0)
    world.add_obstacle(20.0, 5.0, 3.0, 3.0)
    world.set_reference_path([(0, 0), (10, 0), (20, 0), (30, 2)])

    state = world.get_state()
    assert state["obstacle_count"] == 2
    assert state["path_point_num"] == 4
    print("✅ 障碍物与路径添加测试通过")


def test_world_step():
    """测试世界单步推进"""
    world = SimulationWorld()
    world.step(acceleration=2.0, steer_angle=0.0)
    state = world.get_state()
    assert state["vehicle"]["speed"] > 0
    assert state["vehicle"]["x"] > 0
    assert abs(state["vehicle"]["y"]) < 1e-6
    print("✅ 世界单步推进测试通过")


def test_world_reset():
    """测试世界重置功能"""
    world = SimulationWorld()
    # 先让车运动起来
    for _ in range(20):
        world.step(acceleration=2.0, steer_angle=0.1)

    # 重置后车辆归位，障碍物保留
    world.reset()
    state = world.get_state()
    assert state["vehicle"]["speed"] == 0.0
    assert state["vehicle"]["x"] == 0.0
    assert state["vehicle"]["yaw"] == 0.0
    print("✅ 世界重置测试通过")


if __name__ == "__main__":
    test_world_init()
    test_add_obstacle_and_path()
    test_world_step()
    test_world_reset()
    print("\n🎉 仿真世界模块全部测试通过")