# tests/test_hmi.py
from framework.event_bus import EventBus
from hmi.hmi_manager import HMIManager
from config import HMI_INFO, HMI_WARNING, HMI_ALERT, HMI_FAULT


def test_add_and_get_alerts():
    """测试添加告警与查询"""
    bus = EventBus()
    hmi = HMIManager(bus)

    hmi.add_alert(HMI_INFO, "系统上电")
    hmi.add_alert(HMI_WARNING, "车速接近上限")

    alerts = hmi.get_active_alerts()
    assert len(alerts) == 2
    assert alerts[0]["level"] == HMI_WARNING  # 最新的在最前
    print("✅ 告警添加与查询测试通过")


def test_highest_level():
    """测试最高告警等级判断"""
    bus = EventBus()
    hmi = HMIManager(bus)

    assert hmi.get_highest_level() == HMI_INFO

    hmi.add_alert(HMI_WARNING, "测试1")
    assert hmi.get_highest_level() == HMI_WARNING

    hmi.add_alert(HMI_FAULT, "严重故障")
    assert hmi.get_highest_level() == HMI_FAULT

    hmi.clear_all()
    assert hmi.get_highest_level() == HMI_INFO
    print("✅ 最高告警等级测试通过")


def test_event_bus_integration():
    """测试通过事件总线发布告警自动接收"""
    bus = EventBus()
    hmi = HMIManager(bus)

    bus.publish("hmi_alert", {"level": HMI_ALERT, "msg": "传感器异常"})
    alerts = hmi.get_active_alerts()

    assert len(alerts) == 1
    assert alerts[0]["level"] == HMI_ALERT
    assert alerts[0]["msg"] == "传感器异常"
    print("✅ 事件总线集成测试通过")


def test_unsubscribe_on_destroy():
    """测试销毁时取消订阅"""
    bus = EventBus()
    hmi = HMIManager(bus)
    hmi.destroy()

    bus.publish("hmi_alert", {"level": HMI_INFO, "msg": "测试"})
    assert len(hmi.get_active_alerts()) == 0
    print("✅ 取消订阅销毁测试通过")


def test_display_priority_and_auto_clear():
    """Toast：高等级优先；INFO 超时后回落到仍可见的告警。"""
    from hmi.config import ALERT_AUTO_CLEAR_S, ALERT_STICKY_CLEAR_S

    bus = EventBus()
    hmi = HMIManager(bus)
    hmi.add_alert(HMI_INFO, "限速切换", code="speed_limit", t=0.0)
    hmi.add_alert(HMI_ALERT, "请立即接管", code="tor", t=1.0)

    disp = hmi.get_display_alert(now=2.0)
    assert disp is not None
    assert disp["code"] == "tor"
    payload = hmi.to_payload("ACTIVE", now=2.0)
    assert payload["latest"]["code"] == "tor"
    assert payload["highest"] == HMI_ALERT
    assert len(payload["alerts"]) == 2

    now_info_gone = ALERT_AUTO_CLEAR_S + 1.5
    assert now_info_gone < ALERT_STICKY_CLEAR_S + 1.0
    disp2 = hmi.get_display_alert(now=now_info_gone)
    assert disp2 is not None and disp2["code"] == "tor"

    now_all_gone = 1.0 + ALERT_STICKY_CLEAR_S + 0.5
    assert hmi.get_display_alert(now=now_all_gone) is None
    assert len(hmi.get_active_alerts()) == 2
    assert hmi.to_payload("ACTIVE", now=now_all_gone)["latest"] is None


if __name__ == "__main__":
    test_add_and_get_alerts()
    test_highest_level()
    test_event_bus_integration()
    test_unsubscribe_on_destroy()
    test_display_priority_and_auto_clear()
    print("\n🎉 HMI 管理器全部测试通过")
