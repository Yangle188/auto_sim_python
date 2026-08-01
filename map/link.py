# map/link.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class Link:
    """地图路段：折线几何 + 限速。"""

    link_id: str
    points: Tuple[Tuple[float, float], ...]
    speed_limit: float  # m/s

    def __post_init__(self) -> None:
        pts = tuple((float(x), float(y)) for x, y in self.points)
        object.__setattr__(self, "points", pts)
        if len(self.points) < 2:
            raise ValueError(f"Link {self.link_id}: need at least 2 points")
        if self.speed_limit <= 0.0:
            raise ValueError(f"Link {self.link_id}: speed_limit must be > 0")
