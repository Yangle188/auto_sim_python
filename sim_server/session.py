# sim_server/session.py
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from config import (
    DT,
    STATE_OFF,
    STATE_ACTIVE,
    STATE_STANDBY,
    STATE_PASSIVE,
    HMI_INFO,
    HMI_WARNING,
    HMI_ALERT,
)

_ACC_VEL_EPS = 1e-3
from framework.state_machine import (
    AutoDriveStateMachine,
    EV_POWER_ON,
    EV_SELF_CHECK_OK,
    EV_ACTIVATE,
    EV_DEACTIVATE,
    EV_SPEED_OUT_OF_RANGE,
)
from hmi.hmi_manager import (
    CODE_AD_ACTIVATE,
    CODE_AD_EXIT,
    CODE_SPEED_LIMIT,
    CODE_STATE_CHANGE,
    CODE_LC_START,
    CODE_LC_DONE,
    CODE_LC_ABORT,
    CODE_LC_REJECT,
    CODE_FCW,
    CODE_AEB,
    CODE_AEB_CLEAR,
    CODE_ACC,
    CODE_SCENE,
    CODE_LCC,
    CODE_ENGAGE,
)
from framework.config import (
    ACTIVE_LOW_SPEED_THRESHOLD,
    ACTIVE_HIGH_SPEED_THRESHOLD,
)
from framework.event_bus import EventBus
from simulator.world import SimulationWorld, Obstacle
from simulator.config import LANE_WIDTH, NUM_LANES
from hmi.hmi_manager import HMIManager
from perception.lidar_sim import LidarSimulator
from perception.camera_sim import CameraSimulator
from perception.perception_fusion import PerceptionFusion
from control.pure_pursuit import PurePursuit
from control.config import STANDBY_ACC
from planning.path_planner import PathPlanner
from planning.traj_planner import TrajPlanner
from planning.lane_change import LaneChangeController, LC_IDLE, LC_CHANGING, LC_ABORTING
from localization.ekf_localizer import EKFLocalizer
from localization.config import GPS_PERIOD
from prediction.predictor import ObstaclePredictor
from map.map_manager import MapManager
from map.link import Link
from map.route import Route
from map.demo_lane_maps import get_base_map, get_lane_map
from map.lane_map import LaneMap, lanes_from_centerline
from map.road_viz import base_map_lane_markings
from safety.aeb import AEBController, MODE_AEB, MODE_FCW, MODE_NONE

from .scene_schema import SceneConfig, default_scene_config, evaluate_motion


def _resolve_base_map(map_id: Optional[str], route_id: Optional[str] = None):
    if map_id:
        return get_base_map(map_id)
    # 算路生成的 route_id 形如 campus_grid_N7_N3
    if route_id:
        for mid in ("campus_grid", "highway_3lane", "urban_arterial"):
            if str(route_id).startswith(mid):
                return get_base_map(mid)
    return None


def _resolve_lane_map(config: SceneConfig, waypoints: List[Tuple[float, float]]) -> LaneMap:
    lm = get_lane_map(getattr(config, "lane_map_id", None))
    if lm is not None:
        return lm
    # adapter：从导航中心线挤出多车道
    speed = 12.0
    if config.links:
        speed = float(config.links[0].speed_limit)
    return lanes_from_centerline(
        map_id=f"adapter_{config.route_id}",
        centerline=waypoints if len(waypoints) >= 2 else [(0.0, 0.0), (50.0, 0.0)],
        num_lanes=NUM_LANES,
        lane_width=LANE_WIDTH,
        speed_limit=speed,
        title=f"adapter:{config.route_id}",
    )


def _pick_start_lane_id(lane_map: LaneMap, start_index: int) -> str:
    ids = lane_map.lane_ids_by_index(int(start_index))
    if ids:
        # 取链起点：无 predecessor 优先
        for lid in ids:
            if not lane_map.lanes[lid].predecessors:
                return lid
        return ids[0]
    # 回退任意 driving
    for lane in lane_map.lanes.values():
        if lane.lane_type == "driving":
            return lane.lane_id
    return next(iter(lane_map.lanes))


def _polyline_tangent_yaw(
    x: float, y: float, points: List[Tuple[float, float]]
) -> Optional[float]:
    """折线最近点切向航向；点列不足时返回 None。"""
    if len(points) < 2:
        return None
    best_i = 0
    best_d2 = float("inf")
    for i in range(len(points) - 1):
        x0, y0 = float(points[i][0]), float(points[i][1])
        x1, y1 = float(points[i + 1][0]), float(points[i + 1][1])
        dx, dy = x1 - x0, y1 - y0
        seg2 = dx * dx + dy * dy
        if seg2 < 1e-18:
            continue
        t = ((x - x0) * dx + (y - y0) * dy) / seg2
        t = max(0.0, min(1.0, t))
        px, py = x0 + t * dx, y0 + t * dy
        d2 = (px - x) ** 2 + (py - y) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best_i = i
    x0, y0 = float(points[best_i][0]), float(points[best_i][1])
    x1, y1 = float(points[best_i + 1][0]), float(points[best_i + 1][1])
    if math.hypot(x1 - x0, y1 - y0) < 1e-9:
        return None
    return math.atan2(y1 - y0, x1 - x0)


def _initial_pose_from_waypoints(
    waypoints: List[Tuple[float, float]],
) -> Tuple[float, float, float]:
    """路线起点 + 首段切向航向，避免默认朝 +x 在竖向路段上切角冲出车道。"""
    if not waypoints:
        return 0.0, 0.0, 0.0
    x0, y0 = float(waypoints[0][0]), float(waypoints[0][1])
    yaw = 0.0
    for i in range(len(waypoints) - 1):
        dx = float(waypoints[i + 1][0]) - float(waypoints[i][0])
        dy = float(waypoints[i + 1][1]) - float(waypoints[i][1])
        if math.hypot(dx, dy) > 1e-6:
            yaw = math.atan2(dy, dx)
            break
    return x0, y0, yaw


class SimSession:
    """
    可注入场景的一帧步进仿真会话。
    状态：idle | running | paused | finished
    """

    def __init__(self, config: Optional[SceneConfig] = None) -> None:
        self._draft: SceneConfig = config or default_scene_config()
        self._applied: SceneConfig = self._draft.model_copy(deep=True)
        self.status: str = "idle"
        self._build(self._applied)

    @property
    def draft_config(self) -> SceneConfig:
        return self._draft

    @property
    def applied_config(self) -> SceneConfig:
        return self._applied

    def set_draft(self, config: SceneConfig) -> None:
        self._draft = config

    def reset(self, config: Optional[SceneConfig] = None) -> None:
        """用草稿（或显式 config）重建 episode，状态 idle。"""
        if config is not None:
            self._draft = config
        self._applied = self._draft.model_copy(deep=True)
        self._teardown_hmi()
        self._build(self._applied)
        self.status = "idle"

    def start(self) -> None:
        if self.status == "finished":
            self.reset()
        self._view_i = len(self._frames) - 1 if self._frames else -1
        self.status = "running"

    def pause(self) -> None:
        if self.status == "running":
            self.status = "paused"

    def resume(self) -> None:
        if self.status == "paused":
            # 从历史回看恢复时跳回最新帧继续仿真
            self._view_i = len(self._frames) - 1 if self._frames else -1
            self.status = "running"

    def step_once(self) -> Optional[Dict[str, Any]]:
        """
        推进一帧并返回 JSON 友好 snapshot。
        finished / 未 running 时返回 None（paused 时也不推进）。
        """
        if self.status != "running":
            return None
        return self._record_advance()

    def seek_frame(self, frame_i: int) -> Optional[Dict[str, Any]]:
        """跳到历史帧（用于时间轴拖动）；自动暂停。"""
        if not self._frames:
            return None
        self._view_i = max(0, min(len(self._frames) - 1, int(frame_i)))
        if self.status == "running":
            self.status = "paused"
        snap = self._frames[self._view_i]
        self._last_snapshot = snap
        return snap

    def request_activate(self) -> Dict[str, Any]:
        """
        驾驶员主动请求 STANDBY→ACTIVE。
        车速已在允许区间则立即切入；否则挂起，待车速满足后再切入。
        """
        if self.state_machine.get_state() != STATE_STANDBY:
            return {
                "ok": False,
                "pending": False,
                "ad_state": self.state_machine.get_state(),
                "reason": "not_standby",
            }
        already_pending = bool(self._ad_engage_pending)
        self._ad_engage_pending = True
        ok = self._try_engage()
        if ok:
            self._sync_ad_state_into_view()
        else:
            if not already_pending:
                speed = float(self.localizer.get_state().get("speed", 0.0))
                self._sim_log(
                    CODE_ENGAGE,
                    f"激活请求已挂起（当前车速 {speed:.1f} m/s，待进入 5–30 m/s）",
                )
            self._sync_ad_state_into_view()
        return {
            "ok": ok,
            "pending": bool(self._ad_engage_pending),
            "ad_state": self.state_machine.get_state(),
            "reason": None if ok else "speed_out_of_range",
        }

    def request_deactivate(self) -> Dict[str, Any]:
        """驾驶员主动退出 ACTIVE → STANDBY。"""
        if self.state_machine.get_state() != STATE_ACTIVE:
            return {
                "ok": False,
                "ad_state": self.state_machine.get_state(),
                "reason": "not_active",
            }
        speed = float(self.localizer.get_state().get("speed", 0.0))
        ok = self.state_machine.transit(EV_DEACTIVATE, vehicle_speed=speed)
        if ok:
            self._ad_engage_pending = False
            if hasattr(self, "lane_change"):
                self.lane_change.reset(self.lane_change.ego_lane_id)
            self._sync_ad_state_into_view()
        return {
            "ok": ok,
            "ad_state": self.state_machine.get_state(),
            "reason": None if ok else "transit_failed",
        }

    def request_lane_change(self, direction: str) -> Dict[str, Any]:
        """拨杆变道请求（left / right）。"""
        true_state = self.world.vehicle.get_state()
        truth_leads = self._truth_leads()
        result = self.lane_change.request(
            direction,
            speed=float(true_state.get("speed", 0.0)),
            ego_xy=(float(true_state["x"]), float(true_state["y"])),
            leads=truth_leads,
            active=self.state_machine.get_state() == STATE_ACTIVE,
        )
        if result.ok:
            side = "左" if direction.lower() == "left" else "右"
            from_id = self.lane_change.ego_lane_id
            to_id = result.target_lane_id or ""
            from_idx = self.lane_map.lanes[from_id].index if from_id in self.lane_map.lanes else "?"
            to_idx = (
                self.lane_map.lanes[to_id].index if to_id in self.lane_map.lanes else "?"
            )
            self._sim_log(
                CODE_LC_START,
                f"拨杆{side}变道：车道{from_idx} → {to_idx}（{from_id} → {to_id}）",
            )
        else:
            self._sim_log(
                CODE_LC_REJECT,
                f"无法变道：{result.msg or result.reason}",
                level=HMI_WARNING,
            )
        self._sync_ad_state_into_view()
        return {
            "ok": result.ok,
            "reason": result.reason,
            "msg": result.msg,
            "lane_change": self.lane_change.status_payload(),
            "ad_state": self.state_machine.get_state(),
        }

    def _sync_ad_state_into_view(self) -> None:
        """激活/退出瞬间同步到当前展示帧（暂停时不会立刻 step）。"""
        ad = self.state_machine.get_state()
        hmi = self.hmi.to_payload(ad)
        if self._frames and 0 <= self._view_i < len(self._frames):
            fr = dict(self._frames[self._view_i])
            fr["state"] = ad
            fr["hmi"] = hmi
            self._frames[self._view_i] = fr
            self._last_snapshot = fr
        elif self._last_snapshot is not None:
            self._last_snapshot = dict(self._last_snapshot)
            self._last_snapshot["state"] = ad
            self._last_snapshot["hmi"] = hmi

    def _try_engage(self) -> bool:
        if self.state_machine.get_state() != STATE_STANDBY:
            self._ad_engage_pending = False
            return False
        speed = float(self.localizer.get_state().get("speed", 0.0))
        ok = self.state_machine.transit(EV_ACTIVATE, vehicle_speed=speed)
        if ok:
            self._ad_engage_pending = False
        return ok

    def _publish_hmi(
        self,
        msg: str,
        *,
        code: str = "",
        level: str = HMI_INFO,
    ) -> None:
        """兼容旧调用；请优先使用 `_sim_log` 记录关键事件。"""
        self._sim_log(code or CODE_STATE_CHANGE, msg, level=level)

    def _sim_log(
        self,
        code: str,
        msg: str,
        *,
        level: str = HMI_INFO,
    ) -> None:
        """
        仿真事件日志 → HMI 面板。

        习惯：关键功能/场景切换必须打一条可读中文日志（含 code），避免 silently 状态变化。
        """
        self.event_bus.publish(
            topic="hmi_alert",
            data={
                "level": level,
                "msg": msg,
                "code": code,
                "t": float(getattr(self, "sim_time", 0.0) or 0.0),
            },
        )

    def _maybe_hmi_speed_limit(self, v_limit: Optional[float]) -> None:
        """限速变化时推送文言（首帧只记基准，不提示）。"""
        if not self._prev_v_limit_known:
            self._prev_v_limit = v_limit
            self._prev_v_limit_known = True
            if v_limit is not None:
                self._sim_log(
                    CODE_SPEED_LIMIT,
                    f"当前限速基准 {float(v_limit):.1f} m/s",
                )
            return
        prev = self._prev_v_limit
        changed = (prev is None) != (v_limit is None)
        if not changed and prev is not None and v_limit is not None:
            changed = abs(float(prev) - float(v_limit)) > 0.05
        if changed:
            if v_limit is None:
                msg = "限速已解除，恢复巡航设定车速"
            elif prev is None:
                msg = f"限速切换：当前限速 {float(v_limit):.1f} m/s"
            else:
                msg = (
                    f"限速切换：{float(prev):.1f} → {float(v_limit):.1f} m/s"
                )
            self._sim_log(CODE_SPEED_LIMIT, msg)
        self._prev_v_limit = v_limit

    def _maybe_log_acc_lead(self) -> None:
        """ACC 跟车目标出现/丢失时记日志（按帧去重）。"""
        lead = self.traj_planner.last_lead
        present = lead is not None
        if present == self._acc_lead_present:
            return
        self._acc_lead_present = present
        if present and lead is not None:
            self._sim_log(
                CODE_ACC,
                f"ACC 跟车：间距 {float(lead['d_gap']):.1f} m，"
                f"前车 {float(lead['v_lead']):.1f} m/s（{lead.get('source', '?')}）",
            )
        else:
            self._sim_log(CODE_ACC, "ACC 目标丢失 / 前车切出，恢复巡航")

    def step_frame(self, delta: int) -> Optional[Dict[str, Any]]:
        """
        逐帧浏览：delta=-1 上一帧，+1 下一帧。
        在历史中间只改显示索引；在最新帧再下一步则推进仿真并保持 paused。
        """
        if delta == 0:
            return self.current_snapshot()

        if delta < 0:
            if not self._frames:
                return None
            self._view_i = max(0, (self._view_i if self._view_i >= 0 else 0) - 1)
            if self.status == "running":
                self.status = "paused"
            snap = self._frames[self._view_i]
            self._last_snapshot = snap
            return snap

        # delta > 0
        if self._frames and 0 <= self._view_i < len(self._frames) - 1:
            self._view_i += 1
            if self.status == "running":
                self.status = "paused"
            snap = self._frames[self._view_i]
            self._last_snapshot = snap
            return snap

        # 已在最新帧：单步推进仿真
        if self.status == "finished":
            return self.current_snapshot()
        if self.sim_time >= self.total_sim_time:
            self.status = "finished"
            return self.current_snapshot()

        keep_paused = self.status in ("paused", "idle", "finished")
        prev = self.status
        self.status = "running"
        snap = self._record_advance()
        if keep_paused and self.status == "running":
            self.status = "paused" if prev != "idle" else "paused"
        elif keep_paused and self.status == "finished":
            pass
        return snap

    def _record_advance(self) -> Optional[Dict[str, Any]]:
        if self.sim_time >= self.total_sim_time:
            self.status = "finished"
            return None
        snap = self._advance_frame()
        self._frames.append(snap)
        # 限制历史长度，避免内存膨胀
        max_frames = 4000
        if len(self._frames) > max_frames:
            drop = len(self._frames) - max_frames
            self._frames = self._frames[drop:]
        self._view_i = len(self._frames) - 1
        if self.sim_time >= self.total_sim_time:
            self.status = "finished"
        return snap

    def current_snapshot(self) -> Optional[Dict[str, Any]]:
        if self._frames and 0 <= self._view_i < len(self._frames):
            return self._frames[self._view_i]
        return self._last_snapshot

    def status_payload(self) -> Dict[str, Any]:
        n = len(self._frames)
        i = self._view_i if n else -1
        # 整段 episode 预期帧数（时间轴分母）；已录帧 frame_n 可能仍小于它
        frame_total = max(n, int(math.ceil(self.total_sim_time / max(DT, 1e-9) - 1e-9)))
        return {
            "status": self.status,
            "t": float(self._frames[i]["t"]) if 0 <= i < n else self.sim_time,
            "duration_s": self.total_sim_time,
            "frame_i": i,
            "frame_n": n,
            "frame_total": frame_total,
            "scrubbing": bool(n and i >= 0 and i < n - 1),
            "ad_state": self.state_machine.get_state(),
            "ad_engage_pending": bool(self._ad_engage_pending),
            "can_activate": self.state_machine.get_state() == STATE_STANDBY,
            "can_deactivate": self.state_machine.get_state() == STATE_ACTIVE,
            "can_lane_change": self.state_machine.get_state() == STATE_ACTIVE
            and getattr(self, "lane_change", None) is not None
            and self.lane_change.state == LC_IDLE,
            "lane_change": self.lane_change.status_payload()
            if getattr(self, "lane_change", None) is not None
            else None,
        }

    def _teardown_hmi(self) -> None:
        hmi = getattr(self, "hmi", None)
        if hmi is not None:
            try:
                hmi.destroy()
            except Exception:
                pass

    def _build(self, config: SceneConfig) -> None:
        self.event_bus = EventBus()
        self.state_machine = AutoDriveStateMachine()
        self.world = SimulationWorld()
        self.hmi = HMIManager(self.event_bus)
        self.lidar = LidarSimulator()
        self.camera = CameraSimulator()
        self.perception_fusion = PerceptionFusion()
        self.controller = PurePursuit()
        self.controller.reset()
        self.path_planner = PathPlanner()
        self.traj_planner = TrajPlanner()
        self.predictor = ObstaclePredictor()
        self.localizer = EKFLocalizer()
        self.map_mgr = MapManager()
        self.map_mgr.set_route(config.to_route())
        route_wps = self.map_mgr.get_waypoints()

        self.lane_map = _resolve_lane_map(config, route_wps)
        start_lane_id = _pick_start_lane_id(
            self.lane_map, int(getattr(config, "start_lane_index", 1))
        )
        self.lane_change = LaneChangeController(self.lane_map)
        self.lane_change.reset(start_lane_id)
        self.aeb = AEBController()
        self.aeb.reset()
        self._aeb_mode_prev = "none"

        # LCC：参考路径 = 当前车道链中心线
        lcc_path = self.lane_change.lcc_path()
        ref = lcc_path if len(lcc_path) >= 2 else route_wps
        self.world.set_reference_path(ref)

        x0, y0, yaw0 = _initial_pose_from_waypoints(self.world.reference_path)
        self.world.vehicle.reset(x=x0, y=y0, yaw=yaw0, speed=0.0)
        self.localizer.reset(x=x0, y=y0, yaw=yaw0, speed=0.0)

        self._dynamic: List[Tuple[Obstacle, Any]] = []
        for obs_in in config.obstacles:
            self.world.add_obstacle(obs_in.x, obs_in.y, obs_in.width, obs_in.height)
            obs = self.world.obstacles[-1]
            if obs_in.dynamic and obs_in.motion is not None:
                self._dynamic.append((obs, obs_in.motion))

        # 底图 / 车道级标线（可视化）
        self._network_lane_markings: List[Dict[str, Any]] = []
        base = _resolve_base_map(
            getattr(config, "base_map_id", None) or getattr(config, "lane_map_id", None),
            getattr(config, "route_id", None),
        )
        if getattr(config, "lane_map_id", None):
            self._network_lane_markings = self.lane_map.markings_payload()
        elif base is not None:
            self._network_lane_markings = base_map_lane_markings(base)
        else:
            self._network_lane_markings = self.lane_map.markings_payload()

        def on_state_changed(old_state: str, new_state: str) -> None:
            self.event_bus.publish(
                topic="state_change",
                data={"old_state": old_state, "new_state": new_state},
            )
            if old_state == STATE_STANDBY and new_state == STATE_ACTIVE:
                lane = self.lane_change.ego_lane_id
                idx = (
                    self.lane_map.lanes[lane].index
                    if lane in self.lane_map.lanes
                    else "?"
                )
                self._sim_log(
                    CODE_AD_ACTIVATE,
                    f"功能已激活 · LCC 车道{idx}（{lane}）",
                )
            elif old_state == STATE_ACTIVE and new_state == STATE_STANDBY:
                self._sim_log(CODE_AD_EXIT, "功能已退出")
            else:
                self._sim_log(
                    CODE_STATE_CHANGE,
                    f"系统状态：{old_state} → {new_state}",
                )

        self.state_machine.state_change_callback = on_state_changed

        self.sim_time = 0.0
        self.total_sim_time = float(config.duration_s)
        self.power_on_done = False
        self.self_check_done = False
        self._eps = DT * 0.5
        self.fused_obstacles: list = []
        self.predictions: list = []
        self.gps_accum = 0.0
        self._last_snapshot: Optional[Dict[str, Any]] = None
        self._frames: List[Dict[str, Any]] = []
        self._view_i: int = -1
        self._v_cmd = 0.0
        self._steer = 0.0
        self._accel = 0.0
        self._v_limit: Optional[float] = None
        # STANDBY→ACTIVE 需驾驶员主动请求；车速未就绪时挂起，就绪后切入
        self._ad_engage_pending = False
        self._prev_v_limit: Optional[float] = None
        self._prev_v_limit_known = False
        self._aeb_mode_prev = "none"
        self._acc_lead_present = False

        # 场景启动日志（写入 HMI 面板）
        n_obs = len(config.obstacles)
        n_dyn = sum(1 for o in config.obstacles if o.dynamic)
        self._sim_log(
            CODE_SCENE,
            f"场景 {config.route_id} · 底图 {getattr(config, 'lane_map_id', None) or getattr(config, 'base_map_id', None) or 'adapter'} "
            f"· 起步车道{int(getattr(config, 'start_lane_index', 1))} "
            f"· 障碍 {n_obs}（动态 {n_dyn}）· 时长 {config.duration_s:.0f}s",
        )
        self._sim_log(
            CODE_LCC,
            f"LCC 就绪：当前 {start_lane_id}",
        )

    def _update_dynamic_obstacles(self) -> None:
        t = self.sim_time
        for obs, motion in self._dynamic:
            ox, oy = evaluate_motion(motion, t)
            obs.x = ox
            obs.y = oy

    def _truth_leads(self) -> List[Dict[str, float]]:
        """
        真值前车/障碍，供纵向 ACC（避免只靠感知漏检或噪声）。

        - 动态障碍：带速度
        - 静态障碍：v=0（画布放置的静止物也必须能触发制动）
        """
        t = self.sim_time
        out: List[Dict[str, float]] = []
        dynamic_ids = {id(obs) for obs, _ in self._dynamic}
        for obs, motion in self._dynamic:
            x0, y0 = evaluate_motion(motion, t)
            x1, y1 = evaluate_motion(motion, t + max(DT, _ACC_VEL_EPS))
            out.append(
                {
                    "x": float(x0),
                    "y": float(y0),
                    "vx": float((x1 - x0) / max(DT, _ACC_VEL_EPS)),
                    "vy": float((y1 - y0) / max(DT, _ACC_VEL_EPS)),
                    "width": float(obs.width),
                    "height": float(obs.height),
                }
            )
        for obs in self.world.obstacles:
            if id(obs) in dynamic_ids:
                continue
            out.append(
                {
                    "x": float(obs.x),
                    "y": float(obs.y),
                    "vx": 0.0,
                    "vy": 0.0,
                    "width": float(obs.width),
                    "height": float(obs.height),
                }
            )
        return out

    def _sync_nav_from_ego_lane(self) -> None:
        """变道完成后，把 MapManager 导航链切到当前 ego 车道，避免金黄导航线仍停在旧道。"""
        lane_id = self.lane_change.ego_lane_id
        if not lane_id or lane_id not in self.lane_map.lanes:
            return
        chain = self.lane_map.follow_lane_chain(lane_id)
        if not chain:
            return
        links = []
        for lid in chain:
            lane = self.lane_map.get(lid)
            links.append(
                Link(
                    lid,
                    lane.points,
                    lane.speed_limit,
                    name=lane.name or lid,
                    road_class="main",
                    maneuver="straight",
                )
            )
        try:
            self.map_mgr.set_route(Route(f"lcc_{chain[0]}", tuple(links)))
        except ValueError:
            pass

    def _lane_display_payload(self, path: list) -> Dict[str, Any]:
        """
        鸟瞰车道线：绑定 lane_map_id 时用世界系标线（变道可见）；
        否则回退到「path 居中挤出」（旧行为）+ 底图 dim 线。
        """
        ego_center = [list(p) for p in self.lane_change.lcc_path()]
        use_world = bool(getattr(self._applied, "lane_map_id", None)) and bool(
            getattr(self, "_network_lane_markings", None)
        )
        if use_world:
            markings = list(self._network_lane_markings)
            if ego_center:
                markings = list(markings) + [
                    {
                        "role": "ego_lane_center",
                        "style": "solid",
                        "points": ego_center,
                        "source": "ego_lane",
                    }
                ]
            n = max(
                (int(lane.index) for lane in self.lane_map.lanes.values()),
                default=0,
            ) + 1
            return {
                "lane_width": float(self.lane_map.lane_width),
                "num_lanes": int(n),
                "lane_left": [],
                "lane_right": [],
                "lane_markings": markings,
                "ego_lane_centerline": ego_center,
                "use_world_lanes": True,
            }
        lane = self.world.get_lane_boundaries(path if path else self.world.reference_path)
        return {
            "lane_width": float(lane["lane_width"]),
            "num_lanes": int(lane.get("num_lanes", 1)),
            "lane_left": [list(p) for p in lane["left"]],
            "lane_right": [list(p) for p in lane["right"]],
            "lane_markings": [
                {
                    "role": m.get("role", ""),
                    "style": m.get("style", "solid"),
                    "points": [list(p) for p in (m.get("points") or [])],
                }
                for m in (lane.get("markings") or [])
            ],
            "ego_lane_centerline": ego_center,
            "use_world_lanes": False,
        }

    def _advance_frame(self) -> Dict[str, Any]:
        if (
            not self.power_on_done
            and self.sim_time + self._eps >= 0.5
            and self.state_machine.get_state() == STATE_OFF
        ):
            self.state_machine.transit(EV_POWER_ON, vehicle_speed=0)
            self.power_on_done = True

        if (
            not self.self_check_done
            and self.sim_time + self._eps >= 2.5
            and self.state_machine.get_state() == STATE_PASSIVE
        ):
            self.state_machine.transit(EV_SELF_CHECK_OK, vehicle_speed=0)
            self.self_check_done = True

        self._update_dynamic_obstacles()

        true_state = self.world.vehicle.get_state()
        self.lidar.step(
            ego_x=true_state["x"],
            ego_y=true_state["y"],
            ego_yaw=true_state["yaw"],
            true_obstacles=self.world.obstacles,
        )
        self.camera.step(
            ego_x=true_state["x"],
            ego_y=true_state["y"],
            ego_yaw=true_state["yaw"],
            true_obstacles=self.world.obstacles,
        )
        self.perception_fusion.fuse(self.lidar.get_results(), self.camera.get_results())
        self.fused_obstacles = self.perception_fusion.get_results()

        self.event_bus.publish(
            topic="perception_update",
            data={
                "timestamp": self.sim_time,
                "obstacles": [obs.to_dict() for obs in self.fused_obstacles],
            },
        )

        self.predictions = self.predictor.step(self.fused_obstacles, DT)
        est_state = self.localizer.get_state()
        truth_leads = self._truth_leads()

        # 变道状态推进 + LCC / 过渡路径
        lc_tick = self.lane_change.tick(
            DT,
            (float(true_state["x"]), float(true_state["y"])),
            leads=truth_leads,
        )
        if lc_tick.reason == "completed":
            lane = self.lane_change.ego_lane_id
            idx = (
                self.lane_map.lanes[lane].index
                if lane in self.lane_map.lanes
                else "?"
            )
            self._sim_log(
                CODE_LC_DONE,
                f"变道完成 → 车道{idx}（{lane}），恢复 LCC",
            )
            self.world.set_reference_path(self.lane_change.lcc_path())
            self._sync_nav_from_ego_lane()
        elif lc_tick.reason in ("abort_occupied", "timeout", "aborted"):
            self._sim_log(
                CODE_LC_ABORT,
                lc_tick.msg or f"变道取消（{lc_tick.reason}）",
                level=HMI_WARNING,
            )
            self.world.set_reference_path(self.lane_change.lcc_path())
            self._sync_nav_from_ego_lane()

        override = self.lane_change.current_path_override()
        raw_path = override if override else self.lane_change.lcc_path()
        if len(raw_path) < 2:
            raw_path = self.map_mgr.get_waypoints()
        path = self.path_planner.plan(raw_path)

        # 限速：优先当前车道属性，其次 MapManager 前瞻
        v_limit = self.map_mgr.get_speed_limit_ahead(est_state["x"], est_state["y"])
        ego_lane = self.lane_map.lanes.get(self.lane_change.ego_lane_id)
        if ego_lane is not None:
            v_limit = (
                float(ego_lane.speed_limit)
                if v_limit is None
                else min(float(v_limit), float(ego_lane.speed_limit))
            )
        self._maybe_hmi_speed_limit(v_limit)
        acc = 0.0
        steer = 0.0
        state = self.state_machine.get_state()
        v_cmd = self.traj_planner.cruise_speed if v_limit is None else v_limit

        # 横向控制用真值位姿：EKF 位置噪声会诱发 Pure Pursuit 画龙；
        # 规划仍用估计；估计轨迹仅叠加显示。
        ctrl_pose = true_state
        if state == STATE_STANDBY:
            v_cmd = self.traj_planner.plan(
                est_state,
                path,
                self.fused_obstacles,
                self.predictions,
                speed_limit=v_limit,
                leads=truth_leads,
            )
            if v_cmd >= self.traj_planner.cruise_speed - 1e-6:
                _, steer = self.controller.compute(ctrl_pose, path)
                acc = STANDBY_ACC
            else:
                acc, steer = self.controller.compute(
                    ctrl_pose, path, target_speed=v_cmd
                )
        elif state == STATE_ACTIVE:
            v_cmd = self.traj_planner.plan(
                est_state,
                path,
                self.fused_obstacles,
                self.predictions,
                speed_limit=v_limit,
                leads=truth_leads,
            )
            acc, steer = self.controller.compute(ctrl_pose, path, target_speed=v_cmd)

        if state in (STATE_ACTIVE, STATE_STANDBY):
            self._maybe_log_acc_lead()

        # AEB / FCW 仲裁（ACTIVE 与 STANDBY 均可告警；制动盖写在 ACTIVE/STANDBY）
        aeb_res = self.aeb.evaluate(
            true_state,
            path,
            leads=truth_leads,
            enabled=state in (STATE_ACTIVE, STATE_STANDBY),
        )
        if aeb_res.mode != self._aeb_mode_prev:
            if aeb_res.mode == MODE_FCW:
                gap = aeb_res.d_gap
                ttc = aeb_res.ttc
                extra = []
                if gap is not None:
                    extra.append(f"d={gap:.1f}m")
                if ttc is not None:
                    extra.append(f"TTC={ttc:.1f}s")
                suf = f"（{' · '.join(extra)}）" if extra else ""
                self._sim_log(CODE_FCW, f"请注意前方{suf}", level=HMI_WARNING)
            elif aeb_res.mode == MODE_AEB:
                gap = aeb_res.d_gap
                ttc = aeb_res.ttc
                extra = []
                if gap is not None:
                    extra.append(f"d={gap:.1f}m")
                if ttc is not None:
                    extra.append(f"TTC={ttc:.1f}s")
                suf = f"（{' · '.join(extra)}）" if extra else ""
                self._sim_log(
                    CODE_AEB,
                    f"自动紧急制动{suf}",
                    level=HMI_ALERT,
                )
            elif aeb_res.mode == MODE_NONE and self._aeb_mode_prev in (
                MODE_FCW,
                MODE_AEB,
            ):
                self._sim_log(CODE_AEB_CLEAR, "前向威胁解除，退出 FCW/AEB")
            self._aeb_mode_prev = aeb_res.mode
        if aeb_res.acc is not None and state in (STATE_ACTIVE, STATE_STANDBY):
            acc = min(float(acc), float(aeb_res.acc))
            v_cmd = min(v_cmd, max(0.0, float(true_state.get("speed", 0.0)) + float(aeb_res.acc) * DT))

        if v_cmd <= 1e-6 and self.lane_change.state == LC_IDLE:
            steer = 0.0

        self.world.step(acc, steer)
        true_state = self.world.vehicle.get_state()

        self.localizer.predict(acc, steer, DT)
        self.gps_accum += DT
        if self.gps_accum + 1e-12 >= GPS_PERIOD:
            gx, gy = self.localizer.simulate_gps(true_state)
            self.localizer.update_gps(gx, gy)
            self.gps_accum = 0.0

        est_state = self.localizer.get_state()
        current_speed = est_state["speed"]

        state = self.state_machine.get_state()
        if state == STATE_STANDBY:
            # 不再自动激活：需前端「激活」→ request_activate
            if self._ad_engage_pending:
                self._try_engage()
        elif state == STATE_ACTIVE:
            self._ad_engage_pending = False
            overspeed = current_speed > ACTIVE_HIGH_SPEED_THRESHOLD
            # 规划主动减速（跟车/静态刹停/终点）时保持 ACTIVE，避免 ACC 在 5m/s 附近抖回 STANDBY
            intentional_slow = (
                v_cmd < ACTIVE_LOW_SPEED_THRESHOLD - 0.5
                or self.traj_planner.last_lead is not None
                or self.aeb.last.mode == MODE_AEB
            )
            underspeed = (
                current_speed < ACTIVE_LOW_SPEED_THRESHOLD and not intentional_slow
            )
            if overspeed or underspeed:
                self.state_machine.transit(
                    EV_SPEED_OUT_OF_RANGE, vehicle_speed=current_speed
                )

        self.state_machine.step(DT)

        preview = self.controller.get_preview_trajectory(true_state, path)
        lookahead = preview.get("lookahead")
        if lookahead is None:
            lp = self.controller.get_lookahead_point(true_state, path)
            lookahead = list(lp) if lp is not None else None
        self._v_cmd = v_cmd
        self._steer = steer
        self._accel = float(acc)
        self._v_limit = v_limit

        snap = self._to_snapshot(
            true_state=true_state,
            est_state=est_state,
            path=path,
            lookahead=lookahead,
            v_cmd=v_cmd,
            steer=steer,
            v_limit=v_limit,
            accel=float(acc),
            preview=preview,
        )
        self._last_snapshot = snap
        self.sim_time += DT
        return snap

    def _to_snapshot(
        self,
        true_state: dict,
        est_state: dict,
        path: list,
        lookahead: Optional[object],
        v_cmd: float,
        steer: float,
        v_limit: Optional[float],
        accel: float = 0.0,
        preview: Optional[dict] = None,
    ) -> Dict[str, Any]:
        lane = self._lane_display_payload(path)
        lead = self.traj_planner.last_lead
        preview = preview or {}
        # 相机航向跟车道/道路中心线，不跟变道过渡曲线，避免换道时画面跟着拧
        road_pts = self.lane_change.lcc_path()
        if len(road_pts) < 2:
            road_pts = list(self.world.reference_path)
        cam_yaw = _polyline_tangent_yaw(
            float(true_state["x"]), float(true_state["y"]), road_pts
        )
        if cam_yaw is None:
            cam_yaw = float(true_state.get("yaw", 0.0))
        return {
            "t": self.sim_time,
            "state": self.state_machine.get_state(),
            "vehicle": dict(true_state),
            "vehicle_est": dict(est_state),
            "waypoints": [list(p) for p in self.world.reference_path],
            "path": [list(p) for p in path],
            "lookahead": list(lookahead) if lookahead is not None else None,
            "lookahead_path": list(preview.get("path_preview") or []),
            "preview_traj": list(preview.get("arc_preview") or []),
            "lookahead_dist": float(preview.get("ld") or 0.0),
            "lane_width": float(lane["lane_width"]),
            "num_lanes": int(lane.get("num_lanes", 1)),
            "lane_left": lane.get("lane_left") or [],
            "lane_right": lane.get("lane_right") or [],
            "lane_markings": lane.get("lane_markings") or [],
            "ego_lane_centerline": lane.get("ego_lane_centerline") or [],
            "use_world_lanes": bool(lane.get("use_world_lanes")),
            # 底图其他路段车道线（dim 绘制）；世界系模式下与 lane_markings 同源，前端可跳过重复
            "network_lane_markings": []
            if lane.get("use_world_lanes")
            else list(getattr(self, "_network_lane_markings", [])),
            "base_map_id": getattr(self._applied, "base_map_id", None),
            "lane_map_id": getattr(self._applied, "lane_map_id", None),
            "ego_lane_id": self.lane_change.ego_lane_id,
            "lane_index": int(self.lane_map.lanes[self.lane_change.ego_lane_id].index)
            if self.lane_change.ego_lane_id in self.lane_map.lanes
            else None,
            "lane_change": self.lane_change.status_payload(),
            "aeb": {
                "mode": self.aeb.last.mode,
                "d_gap": self.aeb.last.d_gap,
                "ttc": self.aeb.last.ttc,
            },
            "vehicle_geom": self.world.get_vehicle_geom(),
            "obstacles": [
                {
                    "x": o.x,
                    "y": o.y,
                    "width": o.width,
                    "height": o.height,
                }
                for o in self.world.obstacles
            ],
            "fused": [o.to_dict() for o in self.fused_obstacles],
            "predictions": [
                {
                    "obs_id": getattr(p, "obs_id", None),
                    "coasting": bool(getattr(p, "coasting", False)),
                    "vx": float(getattr(p, "vx", 0.0) or 0.0),
                    "vy": float(getattr(p, "vy", 0.0) or 0.0),
                    "trajectory": [list(pt) for pt in (p.trajectory or [])],
                }
                for p in self.predictions
            ],
            "v_cmd": float(v_cmd),
            "steer": float(steer),
            "accel": float(accel),
            "speed_limit": None if v_limit is None else float(v_limit),
            "acc": None
            if lead is None
            else {
                "d_gap": float(lead["d_gap"]),
                "v_lead": float(lead["v_lead"]),
                "source": str(lead["source"]),
            },
            "route_links": self.map_mgr.get_route_links(),
            "session_status": self.status,
            "view": {
                "mode": "heading_up",
                "cam_yaw": float(cam_yaw),
                "lock_road_heading": True,
            },
            "hmi": self.hmi.to_payload(self.state_machine.get_state()),
        }

    def log_line(self, snapshot: Dict[str, Any]) -> str:
        true_state = snapshot["vehicle"]
        est_state = snapshot["vehicle_est"]
        v_limit = snapshot.get("speed_limit")
        loc_err = (
            (est_state["x"] - true_state["x"]) ** 2
            + (est_state["y"] - true_state["y"]) ** 2
        ) ** 0.5
        fusion_count = sum(1 for o in self.fused_obstacles if o.source == "fusion")
        lidar_only = sum(1 for o in self.fused_obstacles if o.source == "lidar_only")
        camera_only = sum(1 for o in self.fused_obstacles if o.source == "camera_only")
        highest_alert = self.hmi.get_highest_level()
        return (
            f"[t={snapshot['t']:5.2f}s] "
            f"状态:{snapshot['state']:<10} | "
            f"车速:{est_state['speed']:5.2f} m/s | "
            f"位置:({true_state['x']:6.2f}, {true_state['y']:5.2f}) | "
            f"估计:({est_state['x']:6.2f}, {est_state['y']:5.2f}) | "
            f"loc_err:{loc_err:4.2f} | "
            f"v_cmd:{snapshot['v_cmd']:5.2f} | "
            f"限速:{(f'{v_limit:5.2f}' if v_limit is not None else '  -  ')} | "
            f"预测:{len(self.predictions)} | "
            f"感知:共{len(self.fused_obstacles)}个"
            f"(融合{fusion_count}/激光{lidar_only}/视觉{camera_only}) | "
            f"告警:{highest_alert}"
        )

    def print_summary(self) -> None:
        print("=" * 70)
        print("仿真结束，最终感知障碍物列表：")
        for idx, obs in enumerate(self.fused_obstacles):
            print(
                f"  {idx+1}. ID:{obs.obs_id} 位置({obs.x:5.1f},{obs.y:5.1f}) "
                f"类别:{obs.category:<10} 置信度:{obs.confidence:.2f} 来源:{obs.source}"
            )
        print("\n当前活跃告警列表：")
        for idx, alert in enumerate(self.hmi.get_active_alerts()):
            print(f"  {idx+1}. [{alert['level']}] {alert['msg']}")
        print("=" * 70)
