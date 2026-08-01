# planning/path_planner.py
import math
from typing import List, Tuple

from .config import PATH_RESOLUTION


class PathPlanner:
    """
    全局路径规划（教学简化版）：将稀疏航点按弧长线性插值密化，
    供 Pure Pursuit 预瞄使用。不做几何绕障。
    """

    def __init__(self, resolution: float = PATH_RESOLUTION):
        self.resolution = resolution

    def plan(
        self,
        waypoints: List[Tuple[float, float]],
    ) -> List[Tuple[float, float]]:
        """
        :param waypoints: 稀疏航点 [(x, y), ...]
        :return: 密化后的路径点列表；点数 < 2 时原样返回副本
        """
        if len(waypoints) < 2:
            return list(waypoints)

        dense: List[Tuple[float, float]] = [waypoints[0]]
        for i in range(len(waypoints) - 1):
            x0, y0 = waypoints[i]
            x1, y1 = waypoints[i + 1]
            seg_len = math.hypot(x1 - x0, y1 - y0)
            if seg_len < 1e-9:
                continue

            # 段内插值点数量（不含终点，终点由下一段起点或最终 append 保证）
            n = max(1, int(math.floor(seg_len / self.resolution)))
            for k in range(1, n + 1):
                t = min(1.0, (k * self.resolution) / seg_len)
                if t >= 1.0 - 1e-12:
                    break
                dense.append((x0 + t * (x1 - x0), y0 + t * (y1 - y0)))

            # 每段终点写入（最后一段终点即全局终点）
            dense.append((x1, y1))

        return dense
