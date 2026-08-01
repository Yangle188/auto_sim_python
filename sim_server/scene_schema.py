# sim_server/scene_schema.py
from __future__ import annotations

from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field, field_validator, model_validator

from map.link import Link
from map.route import Route
from map.demo_routes import build_demo_route, build_urban_turn_route


class LinearMotion(BaseModel):
    type: Literal["linear"] = "linear"
    vx: float = 0.0
    vy: float = 0.0
    x0: float
    y0: float


class RouteLinkIn(BaseModel):
    link_id: str
    points: List[Tuple[float, float]]
    speed_limit: float
    name: str = ""
    road_class: Literal["main", "aux"] = "main"
    maneuver: Literal["straight", "left", "right", "merge", "diverge"] = "straight"

    @field_validator("points")
    @classmethod
    def _min_points(cls, v: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        if len(v) < 2:
            raise ValueError("路段至少需要 2 个点")
        return [(float(x), float(y)) for x, y in v]

    @field_validator("speed_limit")
    @classmethod
    def _positive_speed(cls, v: float) -> float:
        if v <= 0.0:
            raise ValueError("限速必须 > 0")
        return float(v)


class ObstacleIn(BaseModel):
    x: float
    y: float
    width: float = 2.0
    height: float = 2.0
    dynamic: bool = False
    motion: Optional[LinearMotion] = None

    @model_validator(mode="after")
    def _dynamic_needs_motion(self) -> "ObstacleIn":
        if self.dynamic and self.motion is None:
            raise ValueError("动态障碍需要 motion 参数")
        if not self.dynamic:
            self.motion = None
        return self


class SceneConfig(BaseModel):
    route_id: str = "urban_turns"
    links: List[RouteLinkIn]
    obstacles: List[ObstacleIn] = Field(default_factory=list)
    duration_s: float = 35.0

    @field_validator("duration_s")
    @classmethod
    def _positive_duration(cls, v: float) -> float:
        if v <= 0.0:
            raise ValueError("仿真时长必须 > 0")
        return float(v)

    @field_validator("links")
    @classmethod
    def _nonempty_links(cls, v: List[RouteLinkIn]) -> List[RouteLinkIn]:
        if not v:
            raise ValueError("场景至少需要 1 条路段")
        return v

    def to_route(self) -> Route:
        links = tuple(
            Link(
                link.link_id,
                tuple(link.points),
                link.speed_limit,
                name=link.name,
                road_class=link.road_class,
                maneuver=link.maneuver,
            )
            for link in self.links
        )
        return Route(self.route_id, links)


def _route_to_links(route: Route) -> List[RouteLinkIn]:
    out: List[RouteLinkIn] = []
    for link in route.links:
        out.append(
            RouteLinkIn(
                link_id=link.link_id,
                points=list(link.points),
                speed_limit=link.speed_limit,
                name=getattr(link, "name", "") or "",
                road_class=getattr(link, "road_class", "main") or "main",  # type: ignore[arg-type]
                maneuver=getattr(link, "maneuver", "straight") or "straight",  # type: ignore[arg-type]
            )
        )
    return out


def urban_scene_config() -> SceneConfig:
    """默认：左右转 + 主辅路切换。"""
    route = build_urban_turn_route()
    return SceneConfig(
        route_id=route.route_id,
        links=_route_to_links(route),
        obstacles=[
            ObstacleIn(x=25.0, y=4.0, width=2.0, height=2.0),
            ObstacleIn(x=70.0, y=-30.0, width=2.5, height=2.5),
            ObstacleIn(x=110.0, y=-48.0, width=3.0, height=3.0),
            ObstacleIn(x=-8.0, y=0.0, width=2.0, height=2.0),
            ObstacleIn(
                x=30.0,
                y=-10.0,
                width=2.0,
                height=2.0,
                dynamic=True,
                motion=LinearMotion(type="linear", vx=0.0, vy=1.2, x0=30.0, y0=-10.0),
            ),
        ],
        duration_s=35.0,
    )


def simple_scene_config() -> SceneConfig:
    """简易近直线场景（旧 demo）。"""
    route = build_demo_route()
    return SceneConfig(
        route_id=route.route_id,
        links=_route_to_links(route),
        obstacles=[
            ObstacleIn(x=15.0, y=4.0, width=2.0, height=2.0),
            ObstacleIn(x=40.0, y=-4.0, width=2.5, height=2.5),
            ObstacleIn(x=80.0, y=4.5, width=3.0, height=3.0),
            ObstacleIn(x=-10.0, y=0.0, width=2.0, height=2.0),
            ObstacleIn(
                x=60.0,
                y=-8.0,
                width=2.0,
                height=2.0,
                dynamic=True,
                motion=LinearMotion(type="linear", vx=0.0, vy=1.5, x0=60.0, y0=-8.0),
            ),
        ],
        duration_s=20.0,
    )


def default_scene_config() -> SceneConfig:
    return urban_scene_config()


def list_presets() -> Dict[str, dict]:
    """预设场景目录（供前端下拉）。"""
    urban = urban_scene_config()
    simple = simple_scene_config()
    return {
        "urban_turns": {
            "id": "urban_turns",
            "title": "城市：左右转 + 主辅路",
            "description": "主路直行→右转进辅路→辅路直行→左转汇入主路→主路直行",
            "scene": urban.model_dump(),
        },
        "simple": {
            "id": "simple",
            "title": "简易近直线",
            "description": "三段近直线不同限速（适合快速回归）",
            "scene": simple.model_dump(),
        },
    }
