# planning/config.py
from simulator.config import REAR_OVERHANG, VEHICLE_LENGTH

# 路径密化分辨率：相邻密化点弧长间距（m）
PATH_RESOLUTION = 2.0

# 巡航目标车速（m/s），对齐 control.TARGET_SPEED
CRUISE_SPEED = 10.0

# 障碍/终点强制接近时的最低目标车速（m/s）
MIN_SPEED = 1.0

# 车头相对后轴的前向伸出（m）：用于中心距 → 保险杠净空
EGO_FRONT_LENGTH = VEHICLE_LENGTH - REAR_OVERHANG

# 未知尺寸前车/障碍沿路径的半长默认值（m）
DEFAULT_LEAD_HALF_LENGTH = 1.0

# 保险杠净空低于此值时目标车速为 0（m）——紧急刹停
STOP_DISTANCE = 2.5

# 静态/未知速度障碍：净空低于此距离开始线性减速（m）
SLOW_DISTANCE = 28.0

# 本车道横向距离阈值（m）：点到路径折线垂距；约半车道略放大
# 车道宽 3.2m → 半宽 1.6m
OBSTACLE_LATERAL_CLEARANCE = 1.8

# 距路径终点小于此弧长时开始线性减速（m）
# 需覆盖 v≈12m/s、减速度≈3m/s² 的制动距离（v²/2a≈24m），并留余量防冲出路线
END_SLOW_DISTANCE = 40.0

# --- ACC 跟车 ---
# 期望时距（s）：d_des = MIN_GAP + TIME_GAP * v_ego
TIME_GAP = 1.5
# 最小净空（m）
MIN_GAP = 6.0
# 间距误差 → 相对目标速增益（1/s）
FOLLOW_KP = 0.4
# 预测轨进入本车道时的提前量（按未来点判定 cut-in）
CUTIN_LOOKAHEAD_USE_PRED = True

# --- 简单绕障 nudge（同车道横向弓形偏移，非完整变道）---
NUDGE_TRIGGER_MIN = 8.0  # 保险杠净空下限（过近交给 AEB/ACC）
NUDGE_TRIGGER_MAX = 38.0
NUDGE_LAT_FRAC = 0.55  # 相对车道宽的横向幅度
NUDGE_APPROACH_S = 10.0
NUDGE_HOLD_S = 8.0
NUDGE_RETURN_S = 12.0
NUDGE_STATIC_SPEED = 0.5  # |v| 低于此视为静止障碍
NUDGE_DONE_PAST_S = 6.0  # 驶过障碍后结束 nudge

# --- DMS / 脱手计时（ACTIVE 后累计，点「双手在环」清零）---
HANDS_OFF_WARN_S = 6.0
HANDS_OFF_TOR_S = 12.0
