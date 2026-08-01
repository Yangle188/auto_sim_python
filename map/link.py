# map/link.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class Link:
    """地图路段：折线几何 + 限速 + 可选注解（主辅路/机动）。"""

    link_id: str
    points: Tuple[Tuple[float, float], ...]
    speed_limit: float  # m/s
    name: str = ""
    road_class: str = "main"  # main | aux
    maneuver: str = "straight"  # straight | left | right | merge | diverge

    def __post_init__(self) -> None:
        pts = tuple((float(x), float(y)) for x, y in self.points)
        object.__setattr__(self, "points", pts)
        if len(self.points) < 2:
            raise ValueError(f"Link {self.link_id}: need at least 2 points")
        if self.speed_limit <= 0.0:
            raise ValueError(f"Link {self.link_id}: speed_limit must be > 0")
        rc = (self.road_class or "main").lower()
        if rc not in ("main", "aux"):
            raise ValueError(f"Link {self.link_id}: road_class must be main|aux")
        object.__setattr__(self, "road_class", rc)
        mv = (self.maneuver or "straight").lower()
        object.__setattr__(self, "maneuver", mv)
