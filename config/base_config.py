# config/base_config.py
import math

# ====================== 全局底层仿真基础参数 ======================
DT = 0.05                # 仿真步长 s (20Hz)
MAX_SIM_TIME = 300.0     # 最大仿真时长 s
GRAVITY = 9.8            # 重力加速度 m/s²

# ====================== 自动驾驶全局状态枚举【全系统共用】 ======================
STATE_OFF = "OFF"
STATE_PASSIVE = "PASSIVE"
STATE_STANDBY = "STANDBY"
STATE_ACTIVE = "ACTIVE"
STATE_OVERRIDE = "OVERRIDE"

# ====================== HMI告警等级枚举【全系统共用】 ======================
HMI_INFO = "INFO"
HMI_WARN = "WARNING"
HMI_ALERT = "ALERT"
HMI_FAULT = "FAULT"