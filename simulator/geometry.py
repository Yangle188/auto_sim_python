# simulator/geometry.py
"""车道边界偏移与自车后轴系外形。"""
from __future__ import annotations

import math
from typing import List, Sequence, Tuple

from .config import (
    LANE_WIDTH,
    NUM_LANES,
    REAR_OVERHANG,
    VEHICLE_LENGTH,
    VEHICLE_WIDTH,
)

Point = Tuple[float, float]


def offset_polyline(
    points: Sequence[Point],
    lateral: float,
) -> List[Point]:
    """
    沿折线行驶方向，向左为正 lateral（m）做等距偏移。
    节点处用法向平均，保证主辅路拐弯处边界大致连续。
    """
    pts = [(float(x), float(y)) for x, y in points]
    n = len(pts)
    if n == 0:
        return []
    if n == 1:
        return [pts[0]]

    def _unit_tangent(i0: int, i1: int) -> Tuple[float, float]:
        dx = pts[i1][0] - pts[i0][0]
        dy = pts[i1][1] - pts[i0][1]
        L = math.hypot(dx, dy)
        if L < 1e-12:
            return 1.0, 0.0
        return dx / L, dy / L

    out: List[Point] = []
    for i in range(n):
        if i == 0:
            tx, ty = _unit_tangent(0, 1)
        elif i == n - 1:
            tx, ty = _unit_tangent(n - 2, n - 1)
        else:
            t1x, t1y = _unit_tangent(i - 1, i)
            t2x, t2y = _unit_tangent(i, i + 1)
            tx, ty = t1x + t2x, t1y + t2y
            L = math.hypot(tx, ty)
            if L < 1e-12:
                tx, ty = t2x, t2y
            else:
                tx, ty = tx / L, ty / L
        # 左侧法向
        nx, ny = -ty, tx
        out.append((pts[i][0] + nx * lateral, pts[i][1] + ny * lateral))
    return out


def lane_boundaries(
    centerline: Sequence[Point],
    lane_width: float = LANE_WIDTH,
) -> dict:
    """由中心线生成单车道左右边界（左=+half，右=-half）。"""
    half = 0.5 * float(lane_width)
    return {
        "lane_width": float(lane_width),
        "num_lanes": 1,
        "center": [(float(x), float(y)) for x, y in centerline],
        "left": offset_polyline(centerline, half),
        "right": offset_polyline(centerline, -half),
        "markings": [
            {
                "role": "outer_left",
                "style": "solid",
                "points": offset_polyline(centerline, half),
            },
            {
                "role": "outer_right",
                "style": "solid",
                "points": offset_polyline(centerline, -half),
            },
        ],
        "lane_centers": [[(float(x), float(y)) for x, y in centerline]],
    }


def multi_lane_boundaries(
    centerline: Sequence[Point],
    lane_width: float = LANE_WIDTH,
    num_lanes: int = NUM_LANES,
) -> dict:
    """
    以自车中心线为中间车道，生成多车道标线。

    markings:
      - outer_left / outer_right: 实线路缘
      - sep_*: 车道分隔虚线
    lane_left / lane_right: 最外侧边界（兼容旧字段）
    """
    n = max(1, int(num_lanes))
    if n % 2 == 0:
        n += 1  # 保证奇数，自车居中
    half = 0.5 * float(lane_width)
    half_road = 0.5 * n * float(lane_width)

    center = [(float(x), float(y)) for x, y in centerline]
    outer_left = offset_polyline(centerline, half_road)
    outer_right = offset_polyline(centerline, -half_road)

    markings: List[dict] = [
        {"role": "outer_left", "style": "solid", "points": outer_left},
        {"role": "outer_right", "style": "solid", "points": outer_right},
    ]

    # 分隔线：相对中心线 ±1.5w, ±0.5w ...（不含最外缘）
    k = 1
    while (k + 0.5) * float(lane_width) < half_road - 1e-9:
        lat = (k + 0.5) * float(lane_width)
        markings.append(
            {
                "role": f"sep_left_{k}",
                "style": "dashed",
                "points": offset_polyline(centerline, lat),
            }
        )
        markings.append(
            {
                "role": f"sep_right_{k}",
                "style": "dashed",
                "points": offset_polyline(centerline, -lat),
            }
        )
        k += 1
    # 自车车道左右边界（半宽）也作为虚线分隔（与邻道之间）
    if n >= 3:
        markings.append(
            {
                "role": "sep_ego_left",
                "style": "dashed",
                "points": offset_polyline(centerline, half),
            }
        )
        markings.append(
            {
                "role": "sep_ego_right",
                "style": "dashed",
                "points": offset_polyline(centerline, -half),
            }
        )

    lane_centers: List[List[Point]] = []
    # 从左到右：+(n//2) ... 0 ... -(n//2)
    half_n = n // 2
    for i in range(half_n, -half_n - 1, -1):
        if i == 0:
            lane_centers.append(center)
        else:
            lane_centers.append(offset_polyline(centerline, i * float(lane_width)))

    return {
        "lane_width": float(lane_width),
        "num_lanes": n,
        "center": center,
        "left": outer_left,
        "right": outer_right,
        "markings": markings,
        "lane_centers": lane_centers,
    }


def ego_footprint_local(
    length: float = VEHICLE_LENGTH,
    width: float = VEHICLE_WIDTH,
    rear_overhang: float = REAR_OVERHANG,
) -> List[Point]:
    """
    车体矩形角点（车体坐标）：原点 = 后轴中心，+x 朝车头，+y 朝左。
    顺序：左前 → 右前 → 右后 → 左后（闭合多边形）。
    """
    x_rear = -float(rear_overhang)
    x_front = float(length) - float(rear_overhang)
    half_w = 0.5 * float(width)
    return [
        (x_front, half_w),
        (x_front, -half_w),
        (x_rear, -half_w),
        (x_rear, half_w),
    ]


def transform_body_to_world(
    local_pts: Sequence[Point],
    x: float,
    y: float,
    yaw: float,
) -> List[Point]:
    """将车体坐标点变换到世界系（后轴位姿）。"""
    c, s = math.cos(yaw), math.sin(yaw)
    return [(x + c * lx - s * ly, y + s * lx + c * ly) for lx, ly in local_pts]


def ego_footprint_world(
    x: float,
    y: float,
    yaw: float,
    length: float = VEHICLE_LENGTH,
    width: float = VEHICLE_WIDTH,
    rear_overhang: float = REAR_OVERHANG,
) -> List[Point]:
    """后轴 (x,y,yaw) 下的车体矩形世界坐标。"""
    return transform_body_to_world(
        ego_footprint_local(length, width, rear_overhang), x, y, yaw
    )
