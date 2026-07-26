# perception/config.py
import math

# ===================== 激光雷达参数 =====================
LIDAR_MAX_RANGE = 60.0          # 最大检测距离 m
LIDAR_FOV = math.radians(120)   # 水平视场角 rad
LIDAR_POS_NOISE_STD = 0.15      # 位置噪声标准差 m
LIDAR_SIZE_NOISE_STD = 0.08     # 尺寸噪声标准差 m
LIDAR_DETECT_PROB = 0.98        # 近距离检测成功率

# ===================== 摄像头参数 =====================
CAMERA_MAX_RANGE = 80.0         # 最大检测距离 m
CAMERA_FOV = math.radians(150)  # 水平视场角 rad（比激光雷达更广）
CAMERA_POS_NOISE_STD = 0.8      # 位置噪声标准差 m（测距误差大）
CAMERA_SIZE_NOISE_STD = 0.3     # 尺寸噪声标准差 m
CAMERA_DETECT_PROB_NEAR = 0.95  # 近距离检测成功率
CAMERA_DETECT_PROB_FAR = 0.6    # 远距离检测成功率（50m外）
CAMERA_CATEGORIES = ["car", "pedestrian", "barrier"]  # 可识别类别