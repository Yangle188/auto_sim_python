# planning/config.py
# 路径密化分辨率：相邻密化点弧长间距（m）
PATH_RESOLUTION = 2.0

# 巡航目标车速（m/s），对齐 control.TARGET_SPEED
CRUISE_SPEED = 10.0

# 障碍/终点强制接近时的最低目标车速（m/s）
MIN_SPEED = 1.0

# 障碍纵向距离低于此值时目标车速为 0（m）——紧急刹停
STOP_DISTANCE = 5.0

# 静态/未知速度障碍：低于此距离开始线性减速（m）
SLOW_DISTANCE = 25.0

# 本车道横向距离阈值（m）：约半车道，避免邻道误触发
# 车道宽 3.2m → 半宽 1.6m；略放大容错
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
