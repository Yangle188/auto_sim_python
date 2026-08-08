# hmi/config.py
MAX_ACTIVE_ALERTS = 40  # 事件日志容量（HMI 面板滚动列表）

# Toast 自动消失（秒）：按等级；事件日志仍保留全文，仅顶栏提示受此约束
ALERT_AUTO_CLEAR_S = 5.0  # INFO
WARNING_AUTO_CLEAR_S = 8.0
ALERT_STICKY_CLEAR_S = 15.0  # ALERT（FCW/AEB/TOR 等）
FAULT_STICKY_CLEAR_S = 30.0
