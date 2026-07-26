# framework/config.py
# 状态机切换阈值
ACTIVE_LOW_SPEED_THRESHOLD = 5.0    # m/s 最低允许激活自动驾驶车速
ACTIVE_HIGH_SPEED_THRESHOLD = 30.0  # m/s 最高自动驾驶工作车速
OVERRIDE_RECOVERY_TIME = 1.0        # 人工接管后恢复等待时长（预留）
SELF_CHECK_MAX_TIME = 5.0           # PASSIVE自检最大时长 s