# prediction/config.py
# 预测时域步数（不含当前点；trajectory 总长 = HORIZON+1）
PRED_HORIZON = 10

# 预测步长（s）
PRED_DT = 0.2

# 检测与航迹最近邻关联距离阈值（m）
MATCH_DIST = 3.0

# 丢失检测后允许 coast 的最大帧数
MAX_COAST_FRAMES = 5

# 低于此速度视为静止，不外推假运动（m/s）；略高以抑制感知噪声假速度
MIN_SPEED_FOR_MOTION = 1.2

# 速度估计一阶低通系数（0~1，越大越跟新测量）
VEL_LP_ALPHA = 0.35

# 外推前最少确认帧数（抑制单帧噪声建轨乱飞）
MIN_AGE_FOR_PRED = 3

# 输入检测聚类半径（m）：合并同源重复检测
DET_CLUSTER_DIST = 2.0
