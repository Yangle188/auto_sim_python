# safety/config.py
"""FCW / AEB 教学参数。"""

# 保险杠净空阈值（m）与 TTC（s）
FCW_TTC = 2.8
FCW_DIST = 22.0
AEB_TTC = 1.2
AEB_DIST = 8.0

# 紧急制动减速度（m/s²）；与车模 MAX_DECEL 对齐（更负会被限幅）
AEB_DECEL = -3.0

# 相对接近速度下限（m/s），过小不触发
MIN_CLOSING_SPEED = 0.3

# 停车后保持制动
AEB_HOLD_SPEED = 0.35
AEB_HOLD_GAP = 4.0

# 本车道垂距门控
EGO_LANE_LAT = 1.6

# 几何：自车后轴→保险杠
EGO_FRONT_LENGTH = 3.8
DEFAULT_LEAD_HALF_LENGTH = 2.0
