# control/config.py
# 预瞄距离：Ld = clip(LOOKAHEAD_GAIN * v, LOOKAHEAD_MIN, LOOKAHEAD_MAX)
LOOKAHEAD_MIN = 6.0
LOOKAHEAD_MAX = 16.0
LOOKAHEAD_GAIN = 1.35  # m per (m/s)
# 兼容旧名：作为中速默认预瞄参考
LOOKAHEAD_DISTANCE = 8.0

# 目标巡航车速（m/s），ACTIVE 时跟踪这个速度
TARGET_SPEED = 10.0

# 纵向 P 增益：acc = Kp * (v_target - v)
SPEED_KP = 0.5

# STANDBY 时固定加速度（起步用）
STANDBY_ACC = 2.0

# 转角变化率上限（rad/s），抑制画龙
MAX_STEER_RATE = 0.45
