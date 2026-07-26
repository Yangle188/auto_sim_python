# perception/perception_fusion.py
import math
from typing import List
from .base import DetectedObstacle


class PerceptionFusion:
    """多传感器融合模块：空间匹配 + 信息互补"""
    # 匹配距离阈值：小于该值认为是同一个障碍物
    MATCH_THRESHOLD = 1.5

    def __init__(self):
        self._fusion_results: List[DetectedObstacle] = []

    def reset(self) -> None:
        self._fusion_results.clear()

    def get_results(self) -> List[DetectedObstacle]:
        return self._fusion_results.copy()

    def fuse(self, lidar_results: List[DetectedObstacle], camera_results: List[DetectedObstacle]) -> None:
        """
        融合激光雷达与摄像头结果
        规则：
        1. 空间距离小于阈值则匹配为同一障碍物
        2. 位置尺寸以激光雷达为准
        3. 类别信息以摄像头为准
        4. 置信度取两者较高值
        5. 未匹配的单独保留
        """
        self._fusion_results.clear()
        matched_camera_idx = set()

        # 遍历激光雷达结果，尝试匹配摄像头结果
        for lidar_obs in lidar_results:
            best_match_idx = -1
            best_dist = float("inf")

            for cam_idx, cam_obs in enumerate(camera_results):
                if cam_idx in matched_camera_idx:
                    continue
                dist = math.hypot(lidar_obs.x - cam_obs.x, lidar_obs.y - cam_obs.y)
                if dist < self.MATCH_THRESHOLD and dist < best_dist:
                    best_dist = dist
                    best_match_idx = cam_idx

            if best_match_idx >= 0:
                # 匹配成功：融合信息
                cam_obs = camera_results[best_match_idx]
                fused = DetectedObstacle(
                    obs_id=lidar_obs.obs_id,
                    x=lidar_obs.x,          # 位置用激光雷达
                    y=lidar_obs.y,
                    width=lidar_obs.width,  # 尺寸用激光雷达
                    height=lidar_obs.height,
                    confidence=max(lidar_obs.confidence, cam_obs.confidence),
                    category=cam_obs.category,  # 类别用摄像头
                    source="fusion"
                )
                self._fusion_results.append(fused)
                matched_camera_idx.add(best_match_idx)
            else:
                # 未匹配：直接保留激光雷达结果
                lidar_obs.source = "lidar_only"
                self._fusion_results.append(lidar_obs)

        # 补充摄像头未匹配的结果
        for cam_idx, cam_obs in enumerate(camera_results):
            if cam_idx not in matched_camera_idx:
                cam_obs.source = "camera_only"
                self._fusion_results.append(cam_obs)