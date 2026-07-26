# tests/test_state_machine.py
from framework.state_machine import (
    AutoDriveStateMachine,
    EV_POWER_ON,
    EV_POWER_OFF,
    EV_SELF_CHECK_OK,
    EV_ACTIVATE,
    EV_DEACTIVATE,
    EV_DRIVER_OVERRIDE,
    EV_SPEED_OUT_OF_RANGE
)
from config.base_config import (
    STATE_OFF,
    STATE_PASSIVE,
    STATE_STANDBY,
    STATE_ACTIVE,
    STATE_OVERRIDE
)


def test_basic_power_flow():
    """上电下电基础流程：OFF -> PASSIVE -> OFF"""
    sm = AutoDriveStateMachine()
    assert sm.get_state() == STATE_OFF

    # OFF上电
    ok = sm.transit(EV_POWER_ON, vehicle_speed=0)
    assert ok is True
    assert sm.get_state() == STATE_PASSIVE

    # PASSIVE下电
    ok = sm.transit(EV_POWER_OFF, vehicle_speed=0)
    assert ok is True
    assert sm.get_state() == STATE_OFF
    print("✅ 上电下电流程测试通过")


def test_activate_ad():
    """测试正常激活自动驾驶：OFF->PASSIVE->STANDBY->ACTIVE"""
    sm = AutoDriveStateMachine()
    sm.transit(EV_POWER_ON, 0)
    sm.transit(EV_SELF_CHECK_OK, 0)
    assert sm.get_state() == STATE_STANDBY

    # 车速过低，激活失败
    ok = sm.transit(EV_ACTIVATE, vehicle_speed=2.0)
    assert ok is False
    assert sm.get_state() == STATE_STANDBY

    # 车速满足条件，激活成功
    ok = sm.transit(EV_ACTIVATE, vehicle_speed=10.0)
    assert ok is True
    assert sm.get_state() == STATE_ACTIVE
    print("✅ 自动驾驶激活逻辑测试通过")


def test_driver_override():
    """ACTIVE状态驾驶员接管进入OVERRIDE"""
    sm = AutoDriveStateMachine()
    sm.transit(EV_POWER_ON, 0)
    sm.transit(EV_SELF_CHECK_OK, 0)
    sm.transit(EV_ACTIVATE, 10.0)

    ok = sm.transit(EV_DRIVER_OVERRIDE, 10.0)
    assert ok is True
    assert sm.get_state() == STATE_OVERRIDE

    # OVERRIDE无法直接再次激活自动驾驶
    ok = sm.transit(EV_ACTIVATE, 10.0)
    assert ok is False

    # 主动取消，切回STANDBY
    ok = sm.transit(EV_DEACTIVATE, 10.0)
    assert ok is True
    assert sm.get_state() == STATE_STANDBY
    print("✅ 人工接管OVERRIDE逻辑测试通过")


def test_speed_out_range():
    """车速超出范围，ACTIVE降级到STANDBY"""
    sm = AutoDriveStateMachine()
    sm.transit(EV_POWER_ON, 0)
    sm.transit(EV_SELF_CHECK_OK, 0)
    sm.transit(EV_ACTIVATE, 10.0)

    ok = sm.transit(EV_SPEED_OUT_OF_RANGE, 25.0)
    assert ok is True
    assert sm.get_state() == STATE_STANDBY
    print("✅ 车速越限降级测试通过")


if __name__ == "__main__":
    test_basic_power_flow()
    test_activate_ad()
    test_driver_override()
    test_speed_out_range()
    print("\n🎉 全部状态机测试用例执行成功！")