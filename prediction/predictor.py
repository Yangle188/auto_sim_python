# prediction/predictor.py
"""
恒速（CV）障碍预测：最近邻关联 + 短时外推，供 TrajPlanner 前瞻减速。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence, Tuple

from .config import (
    PRED_HORIZON,
    PRED_DT,
    MATCH_DIST,
    MAX_COAST_FRAMES,
    MIN_SPEED_FOR_MOTION,
    VEL_LP_ALPHA,
    MIN_AGE_FOR_PRED,
    DET_CLUSTER_DIST,
)


@dataclass
class PredictedObstacle:
    """单条障碍预测结果。"""

    obs_id: int
    x: float
    y: float
    vx: float
    vy: float
    trajectory: List[Tuple[float, float]] = field(default_factory=list)
    coasting: bool = False


@dataclass
class _Track:
    track_id: int
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    coast_frames: int = 0
    age: int = 0


def _cluster_detections(
    dets: List[Tuple[float, float]],
    cluster_dist: float,
) -> List[Tuple[float, float]]:
    """简单贪婪聚类，抑制同一障碍的多源重复检测。"""
    if not dets:
        return []
    used = [False] * len(dets)
    out: List[Tuple[float, float]] = []
    for i, (x, y) in enumerate(dets):
        if used[i]:
            continue
        sx, sy, n = x, y, 1
        used[i] = True
        for j in range(i + 1, len(dets)):
            if used[j]:
                continue
            if math.hypot(dets[j][0] - x, dets[j][1] - y) <= cluster_dist:
                sx += dets[j][0]
                sy += dets[j][1]
                n += 1
                used[j] = True
        out.append((sx / n, sy / n))
    return out


class ObstaclePredictor:
    """
    对融合检测做简单跟踪，并输出 CV 预测轨迹。
    """

    def __init__(
        self,
        horizon: int = PRED_HORIZON,
        pred_dt: float = PRED_DT,
        match_dist: float = MATCH_DIST,
        max_coast_frames: int = MAX_COAST_FRAMES,
        min_speed_for_motion: float = MIN_SPEED_FOR_MOTION,
        vel_lp_alpha: float = VEL_LP_ALPHA,
        min_age_for_pred: int = MIN_AGE_FOR_PRED,
        det_cluster_dist: float = DET_CLUSTER_DIST,
    ):
        self.horizon = horizon
        self.pred_dt = pred_dt
        self.match_dist = match_dist
        self.max_coast_frames = max_coast_frames
        self.min_speed_for_motion = min_speed_for_motion
        self.vel_lp_alpha = vel_lp_alpha
        self.min_age_for_pred = min_age_for_pred
        self.det_cluster_dist = det_cluster_dist
        self._tracks: Dict[int, _Track] = {}
        self._next_id = 1
        self._predictions: List[PredictedObstacle] = []

    def reset(self) -> None:
        self._tracks.clear()
        self._next_id = 1
        self._predictions.clear()

    def get_predictions(self) -> List[PredictedObstacle]:
        return list(self._predictions)

    def step(
        self,
        detections: Sequence[Any],
        dt: float,
    ) -> List[PredictedObstacle]:
        """
        用本帧融合检测更新航迹并生成预测。
        :param detections: 具有 x/y 属性的检测列表
        :param dt: 仿真步长
        """
        dt = max(float(dt), 1e-6)
        raw: List[Tuple[float, float]] = []
        for d in detections:
            ox = getattr(d, "x", None)
            oy = getattr(d, "y", None)
            if ox is None or oy is None:
                continue
            raw.append((float(ox), float(oy)))
        dets = _cluster_detections(raw, self.det_cluster_dist)

        track_ids = list(self._tracks.keys())
        matched_tracks: set = set()
        matched_dets: set = set()

        pairs: List[Tuple[float, int, int]] = []
        for ti, tid in enumerate(track_ids):
            tr = self._tracks[tid]
            for di, (dx, dy) in enumerate(dets):
                dist = math.hypot(dx - tr.x, dy - tr.y)
                if dist <= self.match_dist:
                    pairs.append((dist, ti, di))
        pairs.sort(key=lambda p: p[0])

        for _, ti, di in pairs:
            if ti in matched_tracks or di in matched_dets:
                continue
            tid = track_ids[ti]
            tr = self._tracks[tid]
            dx, dy = dets[di]
            meas_vx = (dx - tr.x) / dt
            meas_vy = (dy - tr.y) / dt
            a = self.vel_lp_alpha
            if tr.age == 0:
                tr.vx, tr.vy = meas_vx, meas_vy
            else:
                tr.vx = (1.0 - a) * tr.vx + a * meas_vx
                tr.vy = (1.0 - a) * tr.vy + a * meas_vy
            tr.x, tr.y = dx, dy
            tr.coast_frames = 0
            tr.age += 1
            matched_tracks.add(ti)
            matched_dets.add(di)

        for di, (dx, dy) in enumerate(dets):
            if di in matched_dets:
                continue
            tid = self._next_id
            self._next_id += 1
            self._tracks[tid] = _Track(track_id=tid, x=dx, y=dy, age=0)

        to_delete: List[int] = []
        for ti, tid in enumerate(track_ids):
            if ti in matched_tracks:
                continue
            tr = self._tracks[tid]
            tr.x += tr.vx * dt
            tr.y += tr.vy * dt
            tr.coast_frames += 1
            tr.age += 1
            if tr.coast_frames > self.max_coast_frames:
                to_delete.append(tid)
        for tid in to_delete:
            del self._tracks[tid]

        self._predictions = []
        for tid, tr in self._tracks.items():
            speed = math.hypot(tr.vx, tr.vy)
            traj: List[Tuple[float, float]] = [(tr.x, tr.y)]
            moving = (
                tr.age >= self.min_age_for_pred
                and speed >= self.min_speed_for_motion
                and tr.coast_frames == 0
            )
            if moving:
                for k in range(1, self.horizon + 1):
                    traj.append(
                        (
                            tr.x + k * self.pred_dt * tr.vx,
                            tr.y + k * self.pred_dt * tr.vy,
                        )
                    )
            self._predictions.append(
                PredictedObstacle(
                    obs_id=tid,
                    x=tr.x,
                    y=tr.y,
                    vx=tr.vx,
                    vy=tr.vy,
                    trajectory=traj,
                    coasting=tr.coast_frames > 0,
                )
            )
        return self.get_predictions()
