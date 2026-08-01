# planning/config.py
# 路径密化分辨率：相邻密化点弧长间距（m）
PATH_RESOLUTION = 2.0

# 巡航目标车速（m/s），对齐 control.TARGET_SPEED
CRUISE_SPEED = 10.0

# 障碍/终点强制接近时的最低目标车速（m/s）
MIN_SPEED = 1.0

# 障碍纵向距离低于此值时目标车速为 0（m）
STOP_DISTANCE = 5.0

# 障碍纵向距离低于此值开始线性减速（m）
SLOW_DISTANCE = 25.0

# 障碍到路径的横向距离阈值：小于此值视为挡在路径上（m）
OBSTACLE_LATERAL_CLEARANCE = 3.0

# 距路径终点小于此弧长时开始线性减速（m）
END_SLOW_DISTANCE = 15.0
