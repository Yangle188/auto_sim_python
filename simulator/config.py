# simulator/config.py
import math

# --- 运动学 ---
WHEEL_BASE = 2.7  # 轴距 m（后轴 → 前轴）
MAX_SPEED = 25.0
MIN_SPEED = 0.0
MAX_STEER_ANGLE = math.radians(30)
MAX_ACC = 2.0
MAX_DECEL = -3.0

# --- 车道 ---
# 单车道实际宽度；参考路径 = 自车所在车道中心线
LANE_WIDTH = 3.2
# 可视化车道数（奇数；中间为自车车道）
NUM_LANES = 3

# --- 自车外形（状态点 (x,y) = 后轴中心，应落在车道中心线上）---
VEHICLE_WIDTH = 1.96
VEHICLE_LENGTH = 4.8
REAR_OVERHANG = 1.0  # 后轴到车尾
# 前轴到车头 = LENGTH - WHEEL_BASE - REAR_OVERHANG
FRONT_OVERHANG = VEHICLE_LENGTH - WHEEL_BASE - REAR_OVERHANG
