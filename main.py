# main.py
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
from simulator.world import SimulationWorld
from hmi.hmi_manager import HMIManager
from perception.lidar_sim import LidarSimulator
from perception.camera_sim import CameraSimulator
from perception.perception_fusion import PerceptionFusion
from control.pure_pursuit import PurePursuit
from control.config import STANDBY_ACC
from planning.path_planner import PathPlanner
from planning.traj_planner import TrajPlanner
from visualize.renderer import create_renderer
from localization.ekf_localizer import EKFLocalizer
from localization.config import GPS_PERIOD
from prediction.predictor import ObstaclePredictor
from map.map_manager import MapManager
from map.demo_routes import build_demo_route


def _run_episode(renderer) -> str:
    """
    跑一轮仿真。
    :return: \"finished\" | \"replay\" | \"closed\"
    """
    event_bus = EventBus()
    state_machine = AutoDriveStateMachine()
    world = SimulationWorld()
    hmi = HMIManager(event_bus)
    lidar = LidarSimulator()
    camera = CameraSimulator()
    perception_fusion = PerceptionFusion()
    controller = PurePursuit()
    path_planner = PathPlanner()
    traj_planner = TrajPlanner()
    predictor = ObstaclePredictor()
    localizer = EKFLocalizer()
    map_mgr = MapManager()
    map_mgr.set_route(build_demo_route())
    true0 = world.vehicle.get_state()
    localizer.reset(
        x=true0["x"], y=true0["y"], yaw=true0["yaw"], speed=true0["speed"]
    )

    # 静态障碍放在路径旁侧；动态障碍横向穿越路径（供预测/前瞻减速）
    world.add_obstacle(15.0, 4.0, 2.0, 2.0)
    world.add_obstacle(40.0, -4.0, 2.5, 2.5)
    world.add_obstacle(80.0, 4.5, 3.0, 3.0)
    world.add_obstacle(-10.0, 0.0, 2.0, 2.0)
    world.add_obstacle(60.0, -8.0, 2.0, 2.0)
    dynamic_obs = world.obstacles[-1]
    world.set_reference_path(map_mgr.get_waypoints())

    def on_state_changed(old_state: str, new_state: str):
        event_bus.publish(
            topic="state_change",
            data={"old_state": old_state, "new_state": new_state}
        )
        event_bus.publish(
            topic="hmi_alert",
            data={"level": HMI_INFO, "msg": f"系统状态切换：{old_state} → {new_state}"}
        )

    state_machine.state_change_callback = on_state_changed

    sim_time = 0.0
    total_sim_time = 20.0
    power_on_done = False
    self_check_done = False
    _eps = DT * 0.5
    fused_obstacles = []
    predictions = []
    gps_accum = 0.0
    outcome = "finished"

    print("=" * 70)
    print("自动驾驶仿真系统启动")
    print("=" * 70)

    while sim_time < total_sim_time:
        if getattr(renderer, "closed", False):
            outcome = "closed"
            break

        renderer.block_while_paused()
        if renderer.consume_replay_request():
            outcome = "replay"
            break

        if not power_on_done and sim_time + _eps >= 0.5 and state_machine.get_state() == STATE_OFF:
            state_machine.transit(EV_POWER_ON, vehicle_speed=0)
            power_on_done = True

        if not self_check_done and sim_time + _eps >= 2.5 and state_machine.get_state() == STATE_PASSIVE:
            ok = state_machine.transit(EV_SELF_CHECK_OK, vehicle_speed=0)
            self_check_done = True
            if not ok:
                print(f"[t={sim_time:5.2f}s] 自检未通过，保持 PASSIVE")

        dynamic_obs.x = 60.0
        dynamic_obs.y = -8.0 + 1.5 * sim_time

        true_state = world.vehicle.get_state()
        lidar.step(
            ego_x=true_state["x"],
            ego_y=true_state["y"],
            ego_yaw=true_state["yaw"],
            true_obstacles=world.obstacles
        )
        camera.step(
            ego_x=true_state["x"],
            ego_y=true_state["y"],
            ego_yaw=true_state["yaw"],
            true_obstacles=world.obstacles
        )
        perception_fusion.fuse(lidar.get_results(), camera.get_results())
        fused_obstacles = perception_fusion.get_results()

        event_bus.publish(
            topic="perception_update",
            data={
                "timestamp": sim_time,
                "obstacles": [obs.to_dict() for obs in fused_obstacles]
            }
        )

        predictions = predictor.step(fused_obstacles, DT)
        est_state = localizer.get_state()
        path = path_planner.plan(map_mgr.get_waypoints())
        v_limit = map_mgr.get_speed_limit_ahead(est_state["x"], est_state["y"])
        acc = 0.0
        steer = 0.0
        state = state_machine.get_state()
        v_cmd = traj_planner.cruise_speed if v_limit is None else v_limit

        if state == STATE_STANDBY:
            v_cmd = traj_planner.plan(
                est_state, path, fused_obstacles, predictions, speed_limit=v_limit
            )
            if v_cmd >= traj_planner.cruise_speed - 1e-6:
                _, steer = controller.compute(est_state, path)
                acc = STANDBY_ACC
            else:
                acc, steer = controller.compute(
                    est_state, path, target_speed=v_cmd
                )
        elif state == STATE_ACTIVE:
            v_cmd = traj_planner.plan(
                est_state, path, fused_obstacles, predictions, speed_limit=v_limit
            )
            acc, steer = controller.compute(est_state, path, target_speed=v_cmd)

        if v_cmd <= 1e-6:
            steer = 0.0

        world.step(acc, steer)
        true_state = world.vehicle.get_state()

        localizer.predict(acc, steer, DT)
        gps_accum += DT
        if gps_accum + 1e-12 >= GPS_PERIOD:
            gx, gy = localizer.simulate_gps(true_state)
            localizer.update_gps(gx, gy)
            gps_accum = 0.0

        est_state = localizer.get_state()
        current_speed = est_state["speed"]

        state = state_machine.get_state()
        if state == STATE_STANDBY:
            if current_speed >= ACTIVE_LOW_SPEED_THRESHOLD:
                state_machine.transit(EV_ACTIVATE, vehicle_speed=current_speed)
        elif state == STATE_ACTIVE:
            if not (ACTIVE_LOW_SPEED_THRESHOLD <= current_speed <= ACTIVE_HIGH_SPEED_THRESHOLD):
                state_machine.transit(EV_SPEED_OUT_OF_RANGE, vehicle_speed=current_speed)

        state_machine.step(DT)

        lookahead = controller.get_lookahead_point(est_state, path)
        loc_err = (
            (est_state["x"] - true_state["x"]) ** 2
            + (est_state["y"] - true_state["y"]) ** 2
        ) ** 0.5
        renderer.update(
            {
                "t": sim_time,
                "state": state_machine.get_state(),
                "vehicle": true_state,
                "vehicle_est": est_state,
                "waypoints": world.reference_path,
                "path": path,
                "lookahead": lookahead,
                "obstacles": world.obstacles,
                "fused": fused_obstacles,
                "predictions": predictions,
                "v_cmd": v_cmd,
                "steer": steer,
                "speed_limit": v_limit,
                "route_links": map_mgr.get_route_links(),
            }
        )

        highest_alert = hmi.get_highest_level()
        fusion_count = sum(1 for o in fused_obstacles if o.source == "fusion")
        lidar_only = sum(1 for o in fused_obstacles if o.source == "lidar_only")
        camera_only = sum(1 for o in fused_obstacles if o.source == "camera_only")

        print(
            f"[t={sim_time:5.2f}s] "
            f"状态:{state_machine.get_state():<10} | "
            f"车速:{current_speed:5.2f} m/s | "
            f"位置:({true_state['x']:6.2f}, {true_state['y']:5.2f}) | "
            f"估计:({est_state['x']:6.2f}, {est_state['y']:5.2f}) | "
            f"loc_err:{loc_err:4.2f} | "
            f"v_cmd:{v_cmd:5.2f} | "
            f"限速:{(f'{v_limit:5.2f}' if v_limit is not None else '  -  ')} | "
            f"预测:{len(predictions)} | "
            f"感知:共{len(fused_obstacles)}个(融合{fusion_count}/激光{lidar_only}/视觉{camera_only}) | "
            f"告警:{highest_alert}"
        )

        sim_time += DT

    print("=" * 70)
    print("仿真结束，最终感知障碍物列表：")
    for idx, obs in enumerate(fused_obstacles):
        print(
            f"  {idx+1}. ID:{obs.obs_id} 位置({obs.x:5.1f},{obs.y:5.1f}) "
            f"类别:{obs.category:<10} 置信度:{obs.confidence:.2f} 来源:{obs.source}"
        )
    print("\n当前活跃告警列表：")
    for idx, alert in enumerate(hmi.get_active_alerts()):
        print(f"  {idx+1}. [{alert['level']}] {alert['msg']}")
    print("=" * 70)

    hmi.destroy()
    return outcome


def main():
    renderer = create_renderer()
    episode = 0
    while True:
        episode += 1
        if episode > 1:
            print(f"\n>>> 第 {episode} 次播放\n")
        renderer.prepare_replay()
        outcome = _run_episode(renderer)

        if outcome == "closed":
            break
        if outcome == "replay":
            continue

        # 正常结束：保持窗口，等待 Replay 或关闭
        hold = renderer.hold_until_closed()
        if hold != "replay":
            break


if __name__ == "__main__":
    main()
