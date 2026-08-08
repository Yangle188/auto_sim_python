# map/config.py
# 前方限速前瞻弧长（m）：取当前点向前该距离内的最低限速
SPEED_LOOKAHEAD_DIST = 20.0

# 相邻 link 端点衔接容差（m）
LINK_JOIN_TOLERANCE = 0.5

# 接近路口 / 多出口车道末端时触发 auto-maneuver 的剩余弧长（m）
AUTO_MANEUVER_DIST = 40.0
