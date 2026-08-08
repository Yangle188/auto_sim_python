# safety/dms.py
"""DMS 教学：ACTIVE 下脱手计时，超时告警并请求 TOR。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from planning.config import HANDS_OFF_TOR_S, HANDS_OFF_WARN_S


@dataclass
class HandsOffMonitor:
    """
    进入 ACTIVE 后开始累计脱手时间；驾驶员点「双手在环」清零。
    事件：warn → tor（各触发一次，直至双手在环或退出 ACTIVE）。
    """

    warn_s: float = HANDS_OFF_WARN_S
    tor_s: float = HANDS_OFF_TOR_S
    elapsed_s: float = 0.0
    warned: bool = False
    tor_requested: bool = False
    active_tracking: bool = False

    def reset(self) -> None:
        self.elapsed_s = 0.0
        self.warned = False
        self.tor_requested = False
        self.active_tracking = False

    def hands_on(self) -> None:
        """驾驶员确认双手在环。"""
        self.elapsed_s = 0.0
        self.warned = False
        self.tor_requested = False

    def set_thresholds(self, warn_s: float, tor_s: float) -> None:
        """运行时调整阈值（须 0 < warn < tor）。"""
        w = float(warn_s)
        t = float(tor_s)
        if w <= 0.0 or t <= w:
            raise ValueError("hands_off 阈值须满足 0 < warn < tor")
        self.warn_s = w
        self.tor_s = t

    def status_payload(self) -> Dict[str, Any]:
        return {
            "hands_off_s": float(self.elapsed_s),
            "hands_off_warn_s": float(self.warn_s),
            "hands_off_tor_s": float(self.tor_s),
            "warned": bool(self.warned),
            "tor_requested": bool(self.tor_requested),
            "tracking": bool(self.active_tracking),
        }

    def tick(self, dt: float, *, active: bool) -> Optional[str]:
        """返回 'warn' | 'tor' | None。"""
        if not active:
            if self.active_tracking:
                self.reset()
            return None
        if not self.active_tracking:
            self.active_tracking = True
            self.elapsed_s = 0.0
            self.warned = False
            self.tor_requested = False
        self.elapsed_s += float(dt)
        if not self.warned and self.elapsed_s >= float(self.warn_s):
            self.warned = True
            return "warn"
        if not self.tor_requested and self.elapsed_s >= float(self.tor_s):
            self.tor_requested = True
            return "tor"
        return None
