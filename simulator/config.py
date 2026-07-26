# simulator/config.py
import math

WHEEL_BASE = 2.7                 # 轴距 m
MAX_SPEED = 25.0                 # 最大车速 m/s
MIN_SPEED = 0.0
MAX_STEER_ANGLE = math.radians(30)# 前轮最大转角
MAX_ACC = 2.0                    # 最大加速度 m/s²
MAX_DECEL = -3.0                 # 最大减速度 m/s²