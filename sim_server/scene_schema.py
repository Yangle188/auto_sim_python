# sim_server/scene_schema.py
from __future__ import annotations

from typing import Annotated, Dict, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from map.link import Link
from map.route import Route
from map.demo_routes import (
    build_acc_highway_route,
    build_demo_route,
    build_urban_turn_route,
)
from simulator.config import LANE_WIDTH, VEHICLE_LENGTH, VEHICLE_WIDTH


class LinearMotion(BaseModel):
    type: Literal["linear"] = "linear"
    vx: float = 0.0
    vy: float = 0.0
    x0: float
    y0: float


class MotionKeyframe(BaseModel):
    t: float
    x: float
    y: float


class ScriptedMotion(BaseModel):
    """关键帧线性插值运动（用于 cut-in / cut-out 剧本）。"""

    type: Literal["scripted"] = "scripted"
    keyframes: List[MotionKeyframe]

    @field_validator("keyframes")
    @classmethod
    def _min_two(cls, v: List[MotionKeyframe]) -> List[MotionKeyframe]:
        if len(v) < 2:
            raise ValueError("scripted motion 至少需要 2 个关键帧")
        return sorted(v, key=lambda k: k.t)


Motion = Annotated[Union[LinearMotion, ScriptedMotion], Field(discriminator="type")]


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
    motion: Optional[Motion] = None

    @model_validator(mode="after")
    def _dynamic_needs_motion(self) -> "ObstacleIn":
        if self.dynamic and self.motion is None:
            raise ValueError("动态障碍需要 motion 参数")
        if not self.dynamic:
            self.motion = None
        return self


class SceneConfig(BaseModel):
    route_id: str = "acc_highway"
    links: List[RouteLinkIn]
    obstacles: List[ObstacleIn] = Field(default_factory=list)
    duration_s: float = 40.0
    # 非空时 snapshot 附带该底图全网车道线（导航 Route 仍只含选中路径）
    base_map_id: Optional[str] = None

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


def route_to_scene_links(route: Route) -> List[RouteLinkIn]:
    """公开：Route → SceneConfig.links。"""
    return _route_to_links(route)


def evaluate_motion(motion: Motion, t: float) -> Tuple[float, float]:
    """按仿真时间求动态障碍世界坐标。"""
    if isinstance(motion, LinearMotion) or getattr(motion, "type", None) == "linear":
        return (
            float(motion.x0) + float(motion.vx) * t,
            float(motion.y0) + float(motion.vy) * t,
        )

    kfs: List[MotionKeyframe] = list(motion.keyframes)
    if t <= kfs[0].t:
        return float(kfs[0].x), float(kfs[0].y)
    if t >= kfs[-1].t:
        return float(kfs[-1].x), float(kfs[-1].y)
    for i in range(len(kfs) - 1):
        a, b = kfs[i], kfs[i + 1]
        if a.t <= t <= b.t:
            den = b.t - a.t
            u = 0.0 if den <= 1e-12 else (t - a.t) / den
            return (
                float(a.x) + u * (float(b.x) - float(a.x)),
                float(a.y) + u * (float(b.y) - float(a.y)),
            )
    return float(kfs[-1].x), float(kfs[-1].y)


def acc_scene_config() -> SceneConfig:
    """
    默认演示：纵向跟车 → 前车 cut-out 加速 → 邻道 cut-in 减速跟随 → 再 cut-out 回巡航。

    车道宽 3.2m：左道 y=+3.2，自车道 y=0，右道 y=-3.2。
    """
    route = build_acc_highway_route()
    lw = LANE_WIDTH
    lead_w = VEHICLE_WIDTH
    lead_h = VEHICLE_LENGTH * 0.85
    # 剧本关键帧：跟车 → 切出后邻道加速保持超前 → 切入减速跟随 → 再切出
    kfs = [
        MotionKeyframe(t=0.0, x=32.0, y=0.0),
        MotionKeyframe(t=11.0, x=32.0 + 5.5 * 11.0, y=0.0),  # 跟车 vx≈5.5
        MotionKeyframe(t=13.0, x=92.5 + 16.0, y=lw),  # cut-out → 左道
        MotionKeyframe(t=20.0, x=108.5 + 12.0 * 7.0, y=lw),  # 邻道加速保持超前
        MotionKeyframe(t=22.0, x=192.5 + 14.0, y=0.0),  # cut-in（仍在自车前方）
        MotionKeyframe(t=30.0, x=206.5 + 5.5 * 8.0, y=0.0),  # 慢跟
        MotionKeyframe(t=32.0, x=250.5 + 14.0, y=-lw),  # cut-out → 右道
        MotionKeyframe(t=42.0, x=264.5 + 12.0 * 10.0, y=-lw),  # 驶离
    ]
    return SceneConfig(
        route_id=route.route_id,
        links=_route_to_links(route),
        obstacles=[
            ObstacleIn(
                x=kfs[0].x,
                y=kfs[0].y,
                width=lead_w,
                height=lead_h,
                dynamic=True,
                motion=ScriptedMotion(type="scripted", keyframes=kfs),
            ),
        ],
        duration_s=42.0,
    )


def urban_scene_config() -> SceneConfig:
    """城市：左右转 + 主辅路切换。"""
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
    return acc_scene_config()


def list_presets() -> Dict[str, dict]:
    """预设场景目录（供前端下拉）。"""
    acc = acc_scene_config()
    urban = urban_scene_config()
    simple = simple_scene_config()
    return {
        "acc_highway": {
            "id": "acc_highway",
            "title": "三车道：跟车 / Cut-in / Cut-out",
            "description": "本车道跟车巡航 → 前车切出加速 → 邻道切入减速跟随 → 再切出回目标车速",
            "scene": acc.model_dump(),
        },
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
