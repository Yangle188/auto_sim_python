# hmi/hmi_manager.py
from typing import Any, Dict, List, Optional

from config import HMI_INFO, HMI_WARNING, HMI_ALERT, HMI_FAULT
from framework.event_bus import EventBus

from .config import MAX_ACTIVE_ALERTS

# 告警等级优先级映射，数值越大等级越高
_ALERT_LEVEL_PRIORITY = {
    HMI_INFO: 1,
    HMI_WARNING: 2,
    HMI_ALERT: 3,
    HMI_FAULT: 4,
}

# 标准文言 code（前端可按 code 高亮）
CODE_AD_ACTIVATE = "ad_activate"
CODE_AD_EXIT = "ad_exit"
CODE_SPEED_LIMIT = "speed_limit"
CODE_STATE_CHANGE = "state_change"


class HMIManager:
    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        # 活跃告警列表，按时间从新到旧排列
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
        """手动添加一条告警"""
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
        """获取所有活跃告警（拷贝，防止外部修改）"""
        return [dict(a) for a in self._active_alerts]

    def get_highest_level(self) -> str:
        """获取当前最高告警等级，无告警返回INFO"""
        if not self._active_alerts:
            return HMI_INFO

        highest = HMI_INFO
        highest_prio = 1
        for alert in self._active_alerts:
            level = alert["level"]
            prio = _ALERT_LEVEL_PRIORITY.get(level, 1)
            if prio > highest_prio:
                highest = level
                highest_prio = prio
        return highest

    def to_payload(self, ad_state: str) -> Dict[str, Any]:
        """写入 snapshot / 前端 HMI 窗口。"""
        alerts = self.get_active_alerts()
        latest = alerts[0] if alerts else None
        return {
            "ad_state": ad_state,
            "alerts": alerts,
            "latest": latest,
            "highest": self.get_highest_level(),
        }

    def destroy(self):
        """销毁时取消订阅，避免野回调"""
        self._event_bus.unsubscribe("hmi_alert", self._on_alert_received)
