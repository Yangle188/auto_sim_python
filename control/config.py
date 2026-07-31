# control/config.py
# 预瞄距离：Pure Pursuit 向前看多远（m）
LOOKAHEAD_DISTANCE = 8.0

# 目标巡航车速（m/s），ACTIVE 时跟踪这个速度
TARGET_SPEED = 10.0

# 纵向 P 增益：acc = Kp * (v_target - v)
SPEED_KP = 0.5

# STANDBY 时固定加速度（起步用，和现在 main 里一致）
STANDBY_ACC = 2.0