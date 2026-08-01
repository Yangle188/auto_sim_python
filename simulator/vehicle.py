# simulator/vehicle.py
import math
from config import DT
from .config import (
    WHEEL_BASE,
    MAX_SPEED,
    MIN_SPEED,
    MAX_STEER_ANGLE,
    MAX_ACC,
    MAX_DECEL
)


class Vehicle:
    """
    运动学自行车模型。

    状态点 (x, y) = **后轴中心**（应落在车道中心线上）；
    yaw = 航向角 rad；speed = 车速 m/s。
    控制输入：acceleration、steer_angle（前轮转角）。
    """

    def __init__(self):
        # 后轴中心置于原点、朝向 x 轴正方向、静止
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.speed = 0.0

    def reset(self, x=0.0, y=0.0, yaw=0.0, speed=0.0):
        """重置车辆状态"""
        self.x = x
        self.y = y
        self.yaw = yaw
        self.speed = speed

    def get_state(self) -> dict:
        """获取当前车辆状态（x/y 为后轴中心）。"""
        return {
            "x": self.x,
            "y": self.y,
            "yaw": self.yaw,
            "speed": self.speed,
            "ref_point": "rear_axle",
        }

    def step(self, acceleration: float, steer_angle: float):
        """
        单步更新车辆状态（运动学自行车模型，平均速度法）
        :param acceleration: 期望加速度 m/s²
        :param steer_angle: 期望前轮转角 rad
        """
        # 1. 控制量约束裁剪
        acceleration = max(MAX_DECEL, min(MAX_ACC, acceleration))
        steer_angle = max(-MAX_STEER_ANGLE, min(MAX_STEER_ANGLE, steer_angle))

        # 2. 记录本帧初速度
        speed_old = self.speed

        # 3. 更新车速
        self.speed += acceleration * DT
        self.speed = max(MIN_SPEED, min(MAX_SPEED, self.speed))

        # 4. 用平均速度计算位移（物理更准确，匹配匀加速理论公式）
        avg_speed = (speed_old + self.speed) / 2.0

        # 5. 更新航向角，再用平均航向积分位置（避免先改 yaw 再积分导致的一阶偏差）
        yaw_rate = avg_speed / WHEEL_BASE * math.tan(steer_angle)
        yaw_old = self.yaw
        self.yaw += yaw_rate * DT
        avg_yaw = (yaw_old + self.yaw) / 2.0

        # 6. 更新世界坐标位置
        self.x += avg_speed * math.cos(avg_yaw) * DT
        self.y += avg_speed * math.sin(avg_yaw) * DT