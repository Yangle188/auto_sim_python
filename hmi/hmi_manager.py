# hmi/hmi_manager.py
from typing import Any, Dict, List, Optional

from config import HMI_INFO, HMI_WARNING, HMI_ALERT, HMI_FAULT
from framework.event_bus import EventBus

from .config import (
    ALERT_AUTO_CLEAR_S,
    ALERT_STICKY_CLEAR_S,
    FAULT_STICKY_CLEAR_S,
    MAX_ACTIVE_ALERTS,
    WARNING_AUTO_CLEAR_S,
)

# 告警等级优先级映射，数值越大等级越高
_ALERT_LEVEL_PRIORITY = {
    HMI_INFO: 1,
    HMI_WARNING: 2,
    HMI_ALERT: 3,
    HMI_FAULT: 4,
}

_CLEAR_S = {
    HMI_INFO: ALERT_AUTO_CLEAR_S,
    HMI_WARNING: WARNING_AUTO_CLEAR_S,
    HMI_ALERT: ALERT_STICKY_CLEAR_S,
    HMI_FAULT: FAULT_STICKY_CLEAR_S,
}

# 标准文言 / 事件日志 code（前端按 code 显示标签）
CODE_AD_ACTIVATE = "ad_activate"
CODE_AD_EXIT = "ad_exit"
CODE_SPEED_LIMIT = "speed_limit"
CODE_STATE_CHANGE = "state_change"
CODE_LC_START = "lane_change_start"
CODE_LC_DONE = "lane_change_done"
CODE_LC_ABORT = "lane_change_abort"
CODE_LC_REJECT = "lane_change_reject"
CODE_FCW = "fcw"
CODE_AEB = "aeb"
CODE_AEB_CLEAR = "aeb_clear"
CODE_ACC = "acc"
CODE_SCENE = "scene"
CODE_LCC = "lcc"
CODE_ENGAGE = "engage"
CODE_TOR = "tor"
CODE_OVERRIDE = "override"
CODE_AUTO_MANEUVER = "auto_maneuver"
CODE_TEACH = "teach"
CODE_NUDGE = "nudge"
CODE_HANDS_OFF = "hands_off"


def alert_priority(level: str) -> int:
    return _ALERT_LEVEL_PRIORITY.get(level, 1)


def alert_clear_s(level: str) -> float:
    return float(_CLEAR_S.get(level, ALERT_AUTO_CLEAR_S))


class HMIManager:
    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        # 活跃告警列表，按时间从新到旧排列（事件日志）
        self._active_alerts: List[Dict[str, Any]] = []
        # 自动订阅告警主题
        self._event_bus.subscribe("hmi_alert", self._on_alert_received)

    def _on_alert_received(self, data: dict):
        """接收事件总线推送的告警消息"""
        level = data.get("level", HMI_INFO)
        msg = data.get("msg", "")
        code = data.get("code", "")
        t = data.get("t")
        self.add_alert(level, msg, code=code, t=t)

    def add_alert(
        self,
        level: str,
        msg: str,
        code: str = "",
        t: Optional[float] = None,
    ):
        """手动添加一条告警（写入事件日志；toast 由优先级+时效选出）"""
        alert: Dict[str, Any] = {
            "level": level,
            "msg": msg,
            "code": code or "",
        }
        if t is not None:
            alert["t"] = float(t)
        # 最新告警插入队首
        self._active_alerts.insert(0, alert)
        # 超出最大条数时淘汰最旧的
        if len(self._active_alerts) > MAX_ACTIVE_ALERTS:
            self._active_alerts.pop()

    def clear_all(self):
        """清空所有告警"""
        self._active_alerts.clear()

    def get_active_alerts(self) -> List[Dict]:
        """获取所有活跃告警（拷贝，防止外部修改）— 完整事件日志"""
        return [dict(a) for a in self._active_alerts]

    def _is_visible(self, alert: Dict[str, Any], now: Optional[float]) -> bool:
        """Toast 是否仍在展示窗口内（无时间戳则视为一直可见）。"""
        if now is None:
            return True
        t = alert.get("t")
        if t is None:
            return True
        age = float(now) - float(t)
        return age <= alert_clear_s(str(alert.get("level", HMI_INFO)))

    def get_visible_alerts(self, now: Optional[float] = None) -> List[Dict]:
        """仍在 toast 时效内的告警（新→旧）。"""
        return [dict(a) for a in self._active_alerts if self._is_visible(a, now)]

    def get_display_alert(self, now: Optional[float] = None) -> Optional[Dict]:
        """
        当前应展示的顶栏提示：在时效内按等级优先，同级取最新。
        """
        best: Optional[Dict[str, Any]] = None
        best_prio = -1
        for alert in self._active_alerts:
            if not self._is_visible(alert, now):
                continue
            prio = alert_priority(str(alert.get("level", HMI_INFO)))
            if prio > best_prio:
                best = alert
                best_prio = prio
            # 同级已按新→旧遍历，先遇到的即最新，无需替换
        return dict(best) if best is not None else None

    def get_highest_level(self, now: Optional[float] = None) -> str:
        """获取当前最高告警等级（默认仅统计 toast 可见项），无告警返回 INFO"""
        highest = HMI_INFO
        highest_prio = 1
        for alert in self._active_alerts:
            if now is not None and not self._is_visible(alert, now):
                continue
            level = alert["level"]
            prio = alert_priority(level)
            if prio > highest_prio:
                highest = level
                highest_prio = prio
        return highest

    def to_payload(
        self,
        ad_state: str,
        now: Optional[float] = None,
    ) -> Dict[str, Any]:
        """写入 snapshot / 前端 HMI 窗口。"""
        alerts = self.get_active_alerts()
        display = self.get_display_alert(now)
        return {
            "ad_state": ad_state,
            "alerts": alerts,
            "latest": display,  # 优先级 toast（非单纯时间最新）
            "highest": self.get_highest_level(now),
        }

    def destroy(self):
        """销毁时取消订阅，避免野回调"""
        self._event_bus.unsubscribe("hmi_alert", self._on_alert_received)
