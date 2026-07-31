# simulator/world.py
from .vehicle import Vehicle


class Obstacle:
    """静态矩形障碍物"""
    def __init__(self, x: float, y: float, width: float, height: float):
        self.x = x
        self.y = y
        self.width = width
        self.height = height


class SimulationWorld:
    def __init__(self):
        # 主车实例
        self.vehicle = Vehicle()
        # 静态障碍物列表
        self.obstacles = []
        # 参考行驶路径：[(x1, y1), (x2, y2), ...]
        self.reference_path = []

    def reset(self) -> None:
        """重置仿真世界：车辆归位，保留障碍物与路径配置"""
        self.vehicle.reset()

    def add_obstacle(self, x: float, y: float, width: float, height: float) -> None:
        """添加静态矩形障碍物"""
        self.obstacles.append(Obstacle(x, y, width, height))

    def set_reference_path(self, path: list) -> None:
        """
        设置参考路径
        :param path: 路径点列表，格式 [(x1, y1), (x2, y2), ...]
        """
        self.reference_path = path.copy()

    def step(self, acceleration: float, steer_angle: float) -> None:
        """
        推进一帧仿真
        :param acceleration: 期望加速度 m/s²
        :param steer_angle: 期望前轮转角 rad
        """
        self.vehicle.step(acceleration, steer_angle)

    def get_state(self) -> dict:
        """获取当前世界全量状态"""
        return {
            "vehicle": self.vehicle.get_state(),
            "obstacle_count": len(self.obstacles),
            "path_point_num": len(self.reference_path)
        }