# framework/state_machine.py
from config import (
    STATE_OFF,
    STATE_PASSIVE,
    STATE_STANDBY,
    STATE_ACTIVE,
    STATE_OVERRIDE
)
from .config import (
    ACTIVE_LOW_SPEED_THRESHOLD,
    ACTIVE_HIGH_SPEED_THRESHOLD,
    SELF_CHECK_MAX_TIME
)

# ===================== 状态跳转事件定义 =====================
EV_POWER_ON = "POWER_ON"
EV_POWER_OFF = "POWER_OFF"
EV_SELF_CHECK_OK = "SELF_CHECK_OK"
EV_SELF_CHECK_FAIL = "SELF_CHECK_FAIL"
EV_ACTIVATE = "ACTIVATE"
EV_DEACTIVATE = "DEACTIVATE"
EV_DRIVER_OVERRIDE = "DRIVER_OVERRIDE"
EV_SPEED_OUT_OF_RANGE = "SPEED_OUT_OF_RANGE"


class AutoDriveStateMachine:
    def __init__(self):
        self._current_state = STATE_OFF
        self._self_check_timer = 0.0
        self._self_check_failed = False
        self.state_change_callback = None

    def get_state(self) -> str:
        return self._current_state

    def is_self_check_failed(self) -> bool:
        return self._self_check_failed

    def _switch_state(self, new_state: str):
        previous_state = self._current_state
        if previous_state == new_state:
            return
        self._current_state = new_state
        if self.state_change_callback is not None:
            self.state_change_callback(previous_state, new_state)

    def transit(self, event: str, vehicle_speed: float) -> bool:
        """
        状态转移处理函数
        :param event: 触发事件
        :param vehicle_speed: 当前车速 m/s
        :return: 是否转移成功
        """
        curr = self._current_state

        if curr == STATE_OFF:
            if event == EV_POWER_ON:
                self._switch_state(STATE_PASSIVE)
                self._self_check_timer = 0.0
                self._self_check_failed = False
                return True

        elif curr == STATE_PASSIVE:
            if event == EV_POWER_OFF:
                self._switch_state(STATE_OFF)
                return True
            if event == EV_SELF_CHECK_OK:
                if self._self_check_failed:
                    return False
                self._switch_state(STATE_STANDBY)
                return True
            if event == EV_SELF_CHECK_FAIL:
                self._self_check_failed = True
                return True

        elif curr == STATE_STANDBY:
            if event == EV_POWER_OFF:
                self._switch_state(STATE_OFF)
                return True
            if event == EV_SELF_CHECK_FAIL:
                self._self_check_failed = True
                self._switch_state(STATE_PASSIVE)
                return True
            if event == EV_ACTIVATE:
                if ACTIVE_LOW_SPEED_THRESHOLD <= vehicle_speed <= ACTIVE_HIGH_SPEED_THRESHOLD:
                    self._switch_state(STATE_ACTIVE)
                    return True

        elif curr == STATE_ACTIVE:
            if event == EV_POWER_OFF:
                self._switch_state(STATE_OFF)
                return True
            if event in (EV_DEACTIVATE, EV_SPEED_OUT_OF_RANGE, EV_SELF_CHECK_FAIL):
                if event == EV_SELF_CHECK_FAIL:
                    self._self_check_failed = True
                self._switch_state(STATE_STANDBY)
                return True
            if event == EV_DRIVER_OVERRIDE:
                self._switch_state(STATE_OVERRIDE)
                return True

        elif curr == STATE_OVERRIDE:
            if event == EV_POWER_OFF:
                self._switch_state(STATE_OFF)
                return True
            if event == EV_DEACTIVATE:
                self._switch_state(STATE_STANDBY)
                return True

        return False

    def step(self, dt: float):
        """
        时序推进：PASSIVE 阶段累计自检计时，超时视为自检失败。
        :param dt: 步长 s
        """
        if self._current_state == STATE_PASSIVE and not self._self_check_failed:
            self._self_check_timer += dt
            if self._self_check_timer > SELF_CHECK_MAX_TIME:
                self._self_check_failed = True
                self._self_check_timer = SELF_CHECK_MAX_TIME
