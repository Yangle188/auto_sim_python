# map/route.py
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence, Tuple

from .config import LINK_JOIN_TOLERANCE
from .link import Link


@dataclass(frozen=True)
class Route:
    """有序 Link 列表构成的导航路线。"""

    route_id: str
    links: Tuple[Link, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "links", tuple(self.links))
        if not self.links:
            raise ValueError(f"Route {self.route_id}: need at least 1 link")
        self._validate_connectivity()

    def _validate_connectivity(self) -> None:
        for i in range(len(self.links) - 1):
            a = self.links[i]
            b = self.links[i + 1]
            ax, ay = a.points[-1]
            bx, by = b.points[0]
            gap = math.hypot(ax - bx, ay - by)
            if gap > LINK_JOIN_TOLERANCE:
                raise ValueError(
                    f"Route {self.route_id}: links {a.link_id} and {b.link_id} "
                    f"are not connected (gap={gap:.3f} m > {LINK_JOIN_TOLERANCE})"
                )
