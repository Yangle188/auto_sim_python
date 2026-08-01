# tests/test_visualize.py
import matplotlib

matplotlib.use("Agg")

from types import SimpleNamespace

from visualize.renderer import Renderer, NullRenderer, create_renderer
from visualize import config as viz_config
from control.pure_pursuit import PurePursuit
from simulator.world import Obstacle


def _snapshot(**overrides):
    base = {
        "t": 1.0,
        "state": "ACTIVE",
        "vehicle": {"x": 5.0, "y": 0.2, "yaw": 0.1, "speed": 6.0},
        "waypoints": [(0.0, 0.0), (50.0, 0.0), (100.0, 2.0)],
        "path": [(0.0, 0.0), (2.0, 0.0), (4.0, 0.0), (50.0, 0.0)],
        "lookahead": (12.0, 0.0),
        "obstacles": [Obstacle(15.0, 4.0, 2.0, 2.0)],
        "fused": [
            SimpleNamespace(x=15.1, y=3.9, source="fusion"),
            SimpleNamespace(x=40.0, y=-3.8, source="lidar_only"),
        ],
        "v_cmd": 10.0,
        "steer": 0.05,
    }
    base.update(overrides)
    return base


def test_null_renderer_noop():
    """NullRenderer 的 update/close/暂停保持 不抛错"""
    r = NullRenderer()
    r.update(_snapshot())
    r.block_while_paused()
    r.prepare_replay()
    assert r.consume_replay_request() is False
    assert r.hold_until_closed() == "close"
    assert r.paused is False
    r.close()
    print("✅ NullRenderer 测试通过")


def test_create_renderer_respects_enable_flag():
    """ENABLE_VISUALIZE=False 时工厂返回 NullRenderer"""
    old = viz_config.ENABLE_VISUALIZE
    try:
        viz_config.ENABLE_VISUALIZE = False
        r = create_renderer()
        assert isinstance(r, NullRenderer)
    finally:
        viz_config.ENABLE_VISUALIZE = old
    print("✅ create_renderer 开关测试通过")


def test_renderer_update_and_close():
    """Agg 后端下完整 snapshot 可绘制并关闭"""
    r = Renderer(update_every_n=1, pause_sec=0.0)
    r.update(_snapshot())
    r.update(
        _snapshot(
            path=[],
            waypoints=[],
            lookahead=None,
            obstacles=[],
            fused=[],
            vehicle={"x": 0.0, "y": 0.0, "yaw": 0.0, "speed": 0.0},
        )
    )
    r.close()
    # close 后再 update 应安全忽略
    r.update(_snapshot())
    print("✅ Renderer update/close 测试通过")


def test_renderer_pause_and_hold_agg_noop():
    """Agg 下暂停阻塞与结束后保持应立即返回，不挂起"""
    r = Renderer(update_every_n=1, pause_sec=0.0, hold_on_finish=True)
    r.update(_snapshot())
    r._paused = True  # 非交互后端 block_while_paused 仍应立刻返回
    r.block_while_paused()
    assert r.hold_until_closed() == "close"  # Agg：直接 close
    assert r._closed
    print("✅ Agg 暂停/保持测试通过")


def test_renderer_replay_request_flag():
    """重播请求可被设置并消费"""
    r = Renderer(update_every_n=1, pause_sec=0.0, hold_on_finish=False)
    r.update(_snapshot())
    r._request_replay()
    assert r.consume_replay_request() is True
    assert r.consume_replay_request() is False
    r.prepare_replay()
    r.close()
    print("✅ Replay 标志测试通过")


def test_get_lookahead_point_for_viz():
    """控制模块公开预瞄点查询，供可视化使用"""
    ctrl = PurePursuit(lookahead=8.0)
    path = [(0.0, 0.0), (5.0, 0.0), (12.0, 0.0), (30.0, 0.0)]
    pt = ctrl.get_lookahead_point({"x": 0.0, "y": 0.0, "yaw": 0.0, "speed": 0.0}, path)
    assert pt == (12.0, 0.0)
    assert ctrl.get_lookahead_point({"x": 0.0, "y": 0.0}, []) is None
    print("✅ get_lookahead_point 测试通过")


if __name__ == "__main__":
    test_null_renderer_noop()
    test_create_renderer_respects_enable_flag()
    test_renderer_update_and_close()
    test_renderer_pause_and_hold_agg_noop()
    test_renderer_replay_request_flag()
    test_get_lookahead_point_for_viz()
    print("\n🎉 可视化模块全部测试通过")
