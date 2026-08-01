# localization/config.py
# GPS 更新周期（s）；与 DT=0.05 对齐时约每 2 帧一次
GPS_PERIOD = 0.1

# GPS 位置观测标准差（m）；过大时估计轨迹横向乱晃（看起来像画龙）
GPS_STD_XY = 0.08

# 过程噪声对角（x, y, yaw, v）——略收紧，里程计预测更跟手
PROCESS_VAR_X = 0.03 ** 2
PROCESS_VAR_Y = 0.03 ** 2
PROCESS_VAR_YAW = 0.01 ** 2
PROCESS_VAR_V = 0.08 ** 2

# 初始协方差对角
P0_VAR_X = 0.5 ** 2
P0_VAR_Y = 0.5 ** 2
P0_VAR_YAW = 0.1 ** 2
P0_VAR_V = 0.5 ** 2

# GPS 噪声随机种子（None 表示不固定）
GPS_RNG_SEED = 0
