# tests/test_event_bus.py
from framework.event_bus import EventBus


def test_subscribe_and_publish():
    """测试订阅+发布基础功能"""
    bus = EventBus()
    result = None

    def callback(data):
        nonlocal result
        result = data

    bus.subscribe("test_topic", callback)
    bus.publish("test_topic", {"value": 123})

    assert result is not None
    assert result["value"] == 123
    print("✅ 订阅发布基础测试通过")


def test_unsubscribe():
    """测试取消订阅功能"""
    bus = EventBus()
    count = 0

    def callback(data):
        nonlocal count
        count += 1

    bus.subscribe("test_topic", callback)
    bus.publish("test_topic", {})
    assert count == 1

    bus.unsubscribe("test_topic", callback)
    bus.publish("test_topic", {})
    assert count == 1  # 取消后不再触发
    print("✅ 取消订阅测试通过")


def test_clear_all():
    """测试清空所有订阅"""
    bus = EventBus()
    count = 0

    def callback(data):
        nonlocal count
        count += 1

    bus.subscribe("demo1", callback)
    bus.subscribe("demo2", callback)
    bus.clear_all()

    bus.publish("demo1", {})
    bus.publish("demo2", {})
    assert count == 0
    print("✅ 清空所有订阅测试通过")


def test_callback_exception_isolation():
    """单个回调异常不应阻断同主题其他订阅者"""
    bus = EventBus()
    received = []

    def bad(_data):
        raise RuntimeError("boom")

    def good(data):
        received.append(data)

    bus.subscribe("t", bad)
    bus.subscribe("t", good)
    bus.publish("t", {"ok": True})
    assert received == [{"ok": True}]
    print("✅ 回调异常隔离测试通过")


if __name__ == "__main__":
    test_subscribe_and_publish()
    test_unsubscribe()
    test_clear_all()
    test_callback_exception_isolation()
    print("\n🎉 EventBus 全部测试用例通过")