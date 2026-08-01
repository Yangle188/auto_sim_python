# sim_server/session.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from config import DT, STATE_OFF, STATE_ACTIVE, STATE_STANDBY, STATE_PASSIVE, HMI_INFO
from framework.state_machine import (
    AutoDriveStateMachine,
    EV_POWER_ON,
    EV_SELF_CHECK_OK,
    EV_ACTIVATE,
    EV_SPEED_OUT_OF_RANGE,
)
from framework.config import (
    ACTIVE_LOW_SPEED_THRESHOLD,
    ACTIVE_HIGH_SPEED_THRESHOLD,
)
from framework.event_bus import EventBus
from simulator.world import SimulationWorld, Obstacle
from hmi.hmi_manager import HMIManager
from perception.lidar_sim import LidarSimulator
from perception.camera_sim import CameraSimulator
from perception.perception_fusion import PerceptionFusion
from control.pure_pursuit import PurePursuit
from control.config import STANDBY_ACC
from planning.path_planner import PathPlanner
from planning.traj_planner import TrajPlanner
from localization.ekf_localizer import EKFLocalizer
from localization.config import GPS_PERIOD
from prediction.predictor import ObstaclePredictor
from map.map_manager import MapManager

from .scene_schema import SceneConfig, default_scene_config


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
        self.status = "running"

    def pause(self) -> None:
        if self.status == "running":
            self.status = "paused"

    def resume(self) -> None:
        if self.status == "paused":
            self.status = "running"

    def step_once(self) -> Optional[Dict[str, Any]]:
        """
        推进一帧并返回 JSON 友好 snapshot。
        finished / 未 running 时返回 None（paused 时也不推进）。
        """
        if self.status != "running":
            return None
        if self.sim_time >= self.total_sim_time:
            self.status = "finished"
            return None
        snap = self._advance_frame()
        if self.sim_time >= self.total_sim_time:
            self.status = "finished"
        return snap

    def current_snapshot(self) -> Optional[Dict[str, Any]]:
        return self._last_snapshot

    def status_payload(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "t": self.sim_time,
            "duration_s": self.total_sim_time,
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
        self.path_planner = PathPlanner()
        self.traj_planner = TrajPlanner()
        self.predictor = ObstaclePredictor()
        self.localizer = EKFLocalizer()
        self.map_mgr = MapManager()
        self.map_mgr.set_route(config.to_route())

        true0 = self.world.vehicle.get_state()
        self.localizer.reset(
            x=true0["x"], y=true0["y"], yaw=true0["yaw"], speed=true0["speed"]
        )

        self._dynamic: List[Tuple[Obstacle, Any]] = []
        for obs_in in config.obstacles:
            self.world.add_obstacle(obs_in.x, obs_in.y, obs_in.width, obs_in.height)
            obs = self.world.obstacles[-1]
            if obs_in.dynamic and obs_in.motion is not None:
                self._dynamic.append((obs, obs_in.motion))

        self.world.set_reference_path(self.map_mgr.get_waypoints())

        def on_state_changed(old_state: str, new_state: str) -> None:
            self.event_bus.publish(
                topic="state_change",
                data={"old_state": old_state, "new_state": new_state},
            )
            self.event_bus.publish(
                topic="hmi_alert",
                data={
                    "level": HMI_INFO,
                    "msg": f"系统状态切换：{old_state} → {new_state}",
                },
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
        self._v_cmd = 0.0
        self._steer = 0.0
        self._v_limit: Optional[float] = None

    def _update_dynamic_obstacles(self) -> None:
        t = self.sim_time
        for obs, motion in self._dynamic:
            obs.x = motion.x0 + motion.vx * t
            obs.y = motion.y0 + motion.vy * t

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
        path = self.path_planner.plan(self.map_mgr.get_waypoints())
        v_limit = self.map_mgr.get_speed_limit_ahead(est_state["x"], est_state["y"])
        acc = 0.0
        steer = 0.0
        state = self.state_machine.get_state()
        v_cmd = self.traj_planner.cruise_speed if v_limit is None else v_limit

        if state == STATE_STANDBY:
            v_cmd = self.traj_planner.plan(
                est_state, path, self.fused_obstacles, self.predictions, speed_limit=v_limit
            )
            if v_cmd >= self.traj_planner.cruise_speed - 1e-6:
                _, steer = self.controller.compute(est_state, path)
                acc = STANDBY_ACC
            else:
                acc, steer = self.controller.compute(
                    est_state, path, target_speed=v_cmd
                )
        elif state == STATE_ACTIVE:
            v_cmd = self.traj_planner.plan(
                est_state, path, self.fused_obstacles, self.predictions, speed_limit=v_limit
            )
            acc, steer = self.controller.compute(est_state, path, target_speed=v_cmd)

        if v_cmd <= 1e-6:
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
            if current_speed >= ACTIVE_LOW_SPEED_THRESHOLD:
                self.state_machine.transit(EV_ACTIVATE, vehicle_speed=current_speed)
        elif state == STATE_ACTIVE:
            if not (
                ACTIVE_LOW_SPEED_THRESHOLD
                <= current_speed
                <= ACTIVE_HIGH_SPEED_THRESHOLD
            ):
                self.state_machine.transit(
                    EV_SPEED_OUT_OF_RANGE, vehicle_speed=current_speed
                )

        self.state_machine.step(DT)

        lookahead = self.controller.get_lookahead_point(est_state, path)
        self._v_cmd = v_cmd
        self._steer = steer
        self._v_limit = v_limit

        snap = self._to_snapshot(
            true_state=true_state,
            est_state=est_state,
            path=path,
            lookahead=lookahead,
            v_cmd=v_cmd,
            steer=steer,
            v_limit=v_limit,
        )
        self._last_snapshot = snap
        self.sim_time += DT
        return snap

    def _to_snapshot(
        self,
        true_state: dict,
        est_state: dict,
        path: list,
        lookahead: Optional[Tuple[float, float]],
        v_cmd: float,
        steer: float,
        v_limit: Optional[float],
    ) -> Dict[str, Any]:
        lane = self.world.get_lane_boundaries(path if path else self.world.reference_path)
        return {
            "t": self.sim_time,
            "state": self.state_machine.get_state(),
            "vehicle": dict(true_state),
            "vehicle_est": dict(est_state),
            "waypoints": [list(p) for p in self.world.reference_path],
            "path": [list(p) for p in path],
            "lookahead": list(lookahead) if lookahead is not None else None,
            "lane_width": float(lane["lane_width"]),
            "lane_left": [list(p) for p in lane["left"]],
            "lane_right": [list(p) for p in lane["right"]],
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
                    "trajectory": [list(pt) for pt in (p.trajectory or [])],
                }
                for p in self.predictions
            ],
            "v_cmd": float(v_cmd),
            "steer": float(steer),
            "speed_limit": None if v_limit is None else float(v_limit),
            "route_links": self.map_mgr.get_route_links(),
            "session_status": self.status,
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
