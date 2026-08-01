# localization/config.py
# GPS 更新周期（s）；与 DT=0.05 对齐时约每 2 帧一次
GPS_PERIOD = 0.1

# GPS 位置观测标准差（m）
GPS_STD_XY = 0.5

# 过程噪声对角（x, y, yaw, v）——温和，保证闭环仍可跟路径
PROCESS_VAR_X = 0.05 ** 2
PROCESS_VAR_Y = 0.05 ** 2
PROCESS_VAR_YAW = 0.02 ** 2
PROCESS_VAR_V = 0.1 ** 2

# 初始协方差对角
P0_VAR_X = 0.5 ** 2
P0_VAR_Y = 0.5 ** 2
P0_VAR_YAW = 0.1 ** 2
P0_VAR_V = 0.5 ** 2

# GPS 噪声随机种子（None 表示不固定）
GPS_RNG_SEED = 0
