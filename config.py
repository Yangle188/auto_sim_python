## sim config
import math


# =========== basic sim config ==============

DT = 0.05  # 仿真步长
MAX_SIM_TIME = 300 # 最大仿真时间
GRAVITY = 9.8 # G值

# =============== 动力学参数 =================
WHEEL_BASE = 2.7 # 轴距
MAX_VEHICLE_SPEED = 40 #最大车速
MIN_VEHICLE_SPEED = 0
MAX_STEER_ANGEL = math.radians(30) #前轮最大转角
MAX_ACC = 2.0  #最大加速度
MIN_ACC = -5.0 #最大减速度


#=============== 传感器参数 ============
#camera
CAM_RANGE = 50
CAM_FOV = math.radians(60)

#lidar
LIDAR_MAX_RANGE = 60.0
LIDAR_ANGEL_RANGE = math.radians(120)
LIDAR_POINT_NUM = 120

SENSOR_NOISE_STD = 0.3 #感知噪声


# ========= 定位模块参数 ========
GPS_X_NOISE= 0.8
GPS_Y_NOISE= 0.8
IMU_YAW_NOISE= math.radians(0.5)