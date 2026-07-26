# perception/base.py
class DetectedObstacle:
    """感知障碍物统一数据结构"""
    def __init__(
        self,
        obs_id: int,
        x: float,
        y: float,
        width: float,
        height: float,
        confidence: float,
        category: str = "unknown",
        source: str = "unknown"
    ):
        self.obs_id = obs_id
        self.x = x                  # 世界系x坐标
        self.y = y                  # 世界系y坐标
        self.width = width          # 宽度
        self.height = height        # 高度
        self.confidence = confidence  # 检测置信度 0~1
        self.category = category    # 障碍物类别
        self.source = source        # 数据来源：lidar/camera/fusion

    def to_dict(self) -> dict:
        return {
            "obs_id": self.obs_id,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "confidence": self.confidence,
            "category": self.category,
            "source": self.source
        }