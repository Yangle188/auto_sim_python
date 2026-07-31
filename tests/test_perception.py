# tests/test_perception.py
import random
from simulator.world import Obstacle
from perception.lidar_sim import LidarSimulator
from perception.camera_sim import CameraSimulator
from perception.perception_fusion import PerceptionFusion
from perception.base import DetectedObstacle


def test_lidar_range_filter():
    """测试激光雷达距离过滤"""
    random.seed(0)
    lidar = LidarSimulator()
    obs_near = Obstacle(20.0, 0.0, 2.0, 2.0)
    obs_far = Obstacle(100.0, 0.0, 2.0, 2.0)

    lidar.step(0, 0, 0, [obs_near, obs_far])
    results = lidar.get_results()
    assert len(results) == 1
    assert results[0].source == "lidar"
    print("✅ 激光雷达距离过滤测试通过")


def test_camera_category():
    """测试摄像头类别输出"""
    random.seed(0)
    camera = CameraSimulator()
    obs = Obstacle(30.0, 0.0, 2.0, 2.0)

    camera.step(0, 0, 0, [obs])
    results = camera.get_results()
    assert len(results) == 1
    assert results[0].category != "unknown"
    assert results[0].source == "camera"
    print("✅ 摄像头类别识别测试通过")


def test_fusion_match():
    """测试融合层匹配逻辑"""
    random.seed(0)
    lidar = LidarSimulator()
    camera = CameraSimulator()
    fusion = PerceptionFusion()

    # 近距离障碍物大概率被两个传感器同时检测到
    obs = Obstacle(20.0, 0.0, 2.0, 2.0)
    lidar.step(0, 0, 0, [obs])
    camera.step(0, 0, 0, [obs])

    fusion.fuse(lidar.get_results(), camera.get_results())
    fused_results = fusion.get_results()

    assert len(fused_results) >= 1
    # 如果匹配成功，来源为fusion且带有类别
    for r in fused_results:
        if r.source == "fusion":
            assert r.category != "unknown"
    print("✅ 融合层匹配测试通过")


def test_module_reset():
    """测试所有模块重置功能"""
    random.seed(0)
    lidar = LidarSimulator()
    camera = CameraSimulator()
    fusion = PerceptionFusion()
    obs = Obstacle(10.0, 0.0, 2.0, 2.0)

    lidar.step(0, 0, 0, [obs])
    camera.step(0, 0, 0, [obs])
    fusion.fuse(lidar.get_results(), camera.get_results())

    assert len(lidar.get_results()) > 0
    assert len(fusion.get_results()) > 0

    lidar.reset()
    camera.reset()
    fusion.reset()

    assert len(lidar.get_results()) == 0
    assert len(camera.get_results()) == 0
    assert len(fusion.get_results()) == 0
    print("✅ 模块重置测试通过")


def test_fusion_does_not_mutate_inputs():
    """融合未匹配结果时不得改写传感器原始 source"""
    fusion = PerceptionFusion()
    lidar_obs = DetectedObstacle(0, 1.0, 0.0, 2.0, 2.0, 0.9, source="lidar")
    camera_obs = DetectedObstacle(1, 20.0, 0.0, 2.0, 2.0, 0.8, "car", "camera")

    fusion.fuse([lidar_obs], [camera_obs])
    results = fusion.get_results()

    assert lidar_obs.source == "lidar"
    assert camera_obs.source == "camera"
    assert any(r.source == "lidar_only" for r in results)
    assert any(r.source == "camera_only" for r in results)
    print("✅ 融合不污染输入测试通过")


if __name__ == "__main__":
    test_lidar_range_filter()
    test_camera_category()
    test_fusion_match()
    test_module_reset()
    test_fusion_does_not_mutate_inputs()
    print("\n🎉 感知模块（拆分重构版）全部测试通过")