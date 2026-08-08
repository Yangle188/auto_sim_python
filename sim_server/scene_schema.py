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
from map.demo_lane_maps import get_lane_map
from map.lane_map import LaneMap
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
    # 车道级智驾底图；空则从路线中心线 adapter 挤出
    lane_map_id: Optional[str] = None
    # 起步车道 index（自左向右，三车道默认中间=1）
    start_lane_index: int = 1
    # 接近路口时 auto-maneuver 目标：left|right|None（直行不触发切换）
    planned_maneuver: Optional[str] = None
    # True：ACC/AEB/变道间隙用世界真值 leads；False：仅靠感知融合+预测（教学闭环）
    use_truth_leads: bool = True
    # True：横向 Pure Pursuit 用 EKF 估计位姿（易画龙）；False：用真值（默认稳定）
    use_est_pose_lateral: bool = False
    # True：允许同车道简单绕障 nudge
    nudge_enabled: bool = True
    # DMS 脱手：告警 / 自动 TOR 阈值（秒）；须 0 < warn < tor
    hands_off_warn_s: float = 6.0
    hands_off_tor_s: float = 12.0

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

    @model_validator(mode="after")
    def _hands_off_thresholds(self) -> "SceneConfig":
        warn = float(self.hands_off_warn_s)
        tor = float(self.hands_off_tor_s)
        if warn <= 0.0:
            raise ValueError("hands_off_warn_s 必须 > 0")
        if tor <= warn:
            raise ValueError("hands_off_tor_s 必须 > hands_off_warn_s")
        self.hands_off_warn_s = warn
        self.hands_off_tor_s = tor
        return self

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


def _route_from_lane_chain(
    lane_map: LaneMap,
    start_lane_id: str,
    route_id: str,
    *,
    prefer_maneuver: str = "straight",
) -> Route:
    """由车道链生成导航 Route（限速按各 lane 段拆 Link）。"""
    chain = lane_map.follow_lane_chain(
        start_lane_id, prefer_maneuver=prefer_maneuver
    )
    links: List[Link] = []
    for lid in chain:
        lane = lane_map.get(lid)
        if "TURN" in lid or (lane.section_id or "").startswith("UR_TURN"):
            man = prefer_maneuver if prefer_maneuver in ("left", "right") else "left"
        else:
            man = "straight"
        links.append(
            Link(
                lid,
                lane.points,
                lane.speed_limit,
                name=lane.name or lid,
                road_class="main",
                maneuver=man,
            )
        )
    if not links:
        raise ValueError(f"empty lane chain from {start_lane_id}")
    return Route(route_id, tuple(links))


def highway_lcc_scene_config() -> SceneConfig:
    """高速 LCC + 拨杆变道：右道起步，前方右道有静止慢障，可左变道超越。"""
    lm = get_lane_map("highway_3lane")
    assert lm is not None
    # 右道 index=2
    start_ids = lm.lane_ids_by_index(2)
    start_lane = start_ids[0]
    route = _route_from_lane_chain(lm, start_lane, "highway_lcc")
    # 静止障碍放在右道前方（y=-LANE_WIDTH）
    yw = -LANE_WIDTH
    return SceneConfig(
        route_id=route.route_id,
        links=_route_to_links(route),
        obstacles=[
            ObstacleIn(
                x=95.0,
                y=yw,
                width=VEHICLE_WIDTH,
                height=VEHICLE_LENGTH * 0.85,
            ),
        ],
        duration_s=45.0,
        base_map_id="highway_3lane",
        lane_map_id="highway_3lane",
        start_lane_index=2,
        nudge_enabled=False,  # 本场景教拨杆变道，不自动 nudge
    )


def highway_aeb_scene_config() -> SceneConfig:
    """高速 AEB：中道巡航，前方突然出现静止车，触发 FCW→AEB。"""
    lm = get_lane_map("highway_3lane")
    assert lm is not None
    start_lane = lm.lane_ids_by_index(1)[0]
    route = _route_from_lane_chain(lm, start_lane, "highway_aeb")
    return SceneConfig(
        route_id=route.route_id,
        links=_route_to_links(route),
        obstacles=[
            ObstacleIn(
                x=70.0,
                y=0.0,
                width=VEHICLE_WIDTH,
                height=VEHICLE_LENGTH * 0.9,
            ),
        ],
        duration_s=25.0,
        base_map_id="highway_3lane",
        lane_map_id="highway_3lane",
        start_lane_index=1,
        nudge_enabled=False,  # 本场景专测 AEB，不绕开
    )


def nudge_scene_config() -> SceneConfig:
    """高速中道绕障：前方静止障碍，ACTIVE 后同车道横向 nudge 绕行。"""
    lm = get_lane_map("highway_3lane")
    assert lm is not None
    start_lane = lm.lane_ids_by_index(1)[0]
    route = _route_from_lane_chain(lm, start_lane, "nudge_demo")
    return SceneConfig(
        route_id=route.route_id,
        links=_route_to_links(route),
        obstacles=[
            ObstacleIn(
                x=55.0,
                y=0.0,
                width=VEHICLE_WIDTH * 0.9,
                height=VEHICLE_LENGTH * 0.7,
            ),
        ],
        duration_s=35.0,
        base_map_id="highway_3lane",
        lane_map_id="highway_3lane",
        start_lane_index=1,
        nudge_enabled=True,
    )


def acc_scene_config() -> SceneConfig:
    """
    默认演示：纵向跟车 → 前车 cut-out 加速 → 邻道 cut-in 减速跟随 → 再 cut-out 回巡航。

    车道宽 3.2m：左道 y=+3.2，自车道 y=0，右道 y=-3.2。
    绑定 highway_3lane 车道图，自车中道 LCC。
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
        base_map_id="highway_3lane",
        lane_map_id="highway_3lane",
        start_lane_index=1,
    )


def urban_scene_config() -> SceneConfig:
    """城市主干：沿东向中道 LCC，含静止障碍与横穿动态车（AEB/ACC）。"""
    lm = get_lane_map("urban_arterial")
    assert lm is not None
    start_lane = lm.lane_ids_by_index(1)[0]  # UR_EW0_L1
    route = _route_from_lane_chain(lm, start_lane, "urban_arterial")
    return SceneConfig(
        route_id=route.route_id,
        links=_route_to_links(route),
        obstacles=[
            ObstacleIn(x=30.0, y=0.0, width=VEHICLE_WIDTH, height=VEHICLE_LENGTH * 0.8),
            ObstacleIn(
                x=60.0,
                y=-25.0,
                width=2.0,
                height=2.0,
                dynamic=True,
                motion=LinearMotion(type="linear", vx=0.0, vy=2.5, x0=60.0, y0=-25.0),
            ),
        ],
        duration_s=35.0,
        base_map_id="urban_arterial",
        lane_map_id="urban_arterial",
        start_lane_index=1,
    )


def urban_left_scene_config() -> SceneConfig:
    """城市路口左转：接近路口后 auto-maneuver 切到左转连接道 → 北向出口。"""
    lm = get_lane_map("urban_arterial")
    assert lm is not None
    start_lane = lm.lane_ids_by_index(1)[0]
    # 导航金黄线展示左转链；LCC 初始仍直行，临近路口再切换
    route = _route_from_lane_chain(
        lm, start_lane, "urban_left", prefer_maneuver="left"
    )
    return SceneConfig(
        route_id=route.route_id,
        links=_route_to_links(route),
        obstacles=[],
        duration_s=40.0,
        base_map_id="urban_arterial",
        lane_map_id="urban_arterial",
        start_lane_index=1,
        planned_maneuver="left",
    )


def urban_turns_scene_config() -> SceneConfig:
    """旧城市左右转路线（兼容）。"""
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
    return highway_lcc_scene_config()


def list_presets() -> Dict[str, dict]:
    """预设场景目录（供前端下拉）。"""
    highway_lcc = highway_lcc_scene_config()
    highway_aeb = highway_aeb_scene_config()
    nudge = nudge_scene_config()
    acc = acc_scene_config()
    urban = urban_scene_config()
    urban_left = urban_left_scene_config()
    urban_turns = urban_turns_scene_config()
    simple = simple_scene_config()
    return {
        "highway_lcc": {
            "id": "highway_lcc",
            "title": "高速：LCC + 拨杆变道",
            "description": "右道起步，前方静止障碍；激活后拨杆左变道超越，实线段不可换道",
            "scene": highway_lcc.model_dump(),
        },
        "highway_aeb": {
            "id": "highway_aeb",
            "title": "高速：FCW / AEB",
            "description": "中道接近静止前车，先 FCW 再 AEB 紧急制动",
            "scene": highway_aeb.model_dump(),
        },
        "nudge_demo": {
            "id": "nudge_demo",
            "title": "高速：同车道绕障 nudge",
            "description": "中道前方静止障碍；激活后路径横向弓形绕行（非完整变道）",
            "scene": nudge.model_dump(),
        },
        "acc_highway": {
            "id": "acc_highway",
            "title": "三车道：跟车 / Cut-in / Cut-out",
            "description": "本车道跟车巡航 → 前车切出加速 → 邻道切入减速跟随 → 再切出回目标车速",
            "scene": acc.model_dump(),
        },
        "urban_arterial": {
            "id": "urban_arterial",
            "title": "城市：主干+路口",
            "description": "东向主干 LCC，静止障碍 + 路口横穿动态车",
            "scene": urban.model_dump(),
        },
        "urban_left": {
            "id": "urban_left",
            "title": "城市：路口左转",
            "description": "东向接近路口后自动切左转连接道，驶入北向出口",
            "scene": urban_left.model_dump(),
        },
        "urban_turns": {
            "id": "urban_turns",
            "title": "城市：左右转 + 主辅路",
            "description": "主路直行→右转进辅路→辅路直行→左转汇入主路→主路直行",
            "scene": urban_turns.model_dump(),
        },
        "simple": {
            "id": "simple",
            "title": "简易近直线",
            "description": "三段近直线不同限速（适合快速回归）",
            "scene": simple.model_dump(),
        },
    }
