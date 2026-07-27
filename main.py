# main.py
from config import DT, STATE_ACTIVE, STATE_STANDBY, STATE_PASSIVE, HMI_INFO
from framework.state_machine import (
    AutoDriveStateMachine,
    EV_POWER_ON,
    EV_SELF_CHECK_OK,
    EV_ACTIVATE
)
from framework.config import ACTIVE_LOW_SPEED_THRESHOLD
from framework.event_bus import EventBus
from simulator.world import SimulationWorld
from hmi.hmi_manager import HMIManager
# 新增：感知模块导入
from perception.lidar_sim import LidarSimulator
from perception.camera_sim import CameraSimulator
from perception.perception_fusion import PerceptionFusion


def main():
    # ===================== 1. 初始化全局核心组件 =====================
    event_bus = EventBus()
    state_machine = AutoDriveStateMachine()
    world = SimulationWorld()
    hmi = HMIManager(event_bus)
    # 新增：感知三件套实例化
    lidar = LidarSimulator()
    camera = CameraSimulator()
    perception_fusion = PerceptionFusion()

    # ===================== 2. 预加载仿真场景 =====================
    # 添加测试障碍物，验证感知距离、FOV、融合效果
    world.add_obstacle(15.0, 0.0, 2.0, 2.0)    # 正前方近距离
    world.add_obstacle(40.0, 3.0, 2.5, 2.5)    # 中距离偏右
    world.add_obstacle(80.0, 0.0, 3.0, 3.0)    # 超远距离（激光雷达检测不到）
    world.add_obstacle(-10.0, 0.0, 2.0, 2.0)   # 正后方（超出FOV）
    # 设置参考路径
    world.set_reference_path([(0, 0), (50, 0), (100, 2)])

    # ===================== 3. 建立模块间事件关联 =====================
    # 状态机状态变更时：发布事件总线消息 + 推送HMI提示
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

    # ===================== 4. 仿真运行参数初始化 =====================
    sim_time = 0.0
    total_sim_time = 20.0
    self_check_done = False

    print("=" * 70)
    print("自动驾驶仿真系统启动（感知模块已接入）")
    print("=" * 70)

    # ===================== 5. 仿真主循环 =====================
    while sim_time < total_sim_time:
        # ---------- 5.1 固定时序事件触发 ----------
        if sim_time >= 0.5 and state_machine.get_state() == "OFF":
            state_machine.transit(EV_POWER_ON, vehicle_speed=0)

        if sim_time >= 2.5 and not self_check_done and state_machine.get_state() == STATE_PASSIVE:
            state_machine.transit(EV_SELF_CHECK_OK, vehicle_speed=0)
            self_check_done = True

        # ---------- 5.2 计算控制量 + 物理世界步进 ----------
        acc = 0.0
        steer = 0.0
        current_speed = world.vehicle.speed

        if state_machine.get_state() == STATE_STANDBY:
            acc = 2.0
        elif state_machine.get_state() == STATE_ACTIVE:
            target_speed = 10.0
            acc = (target_speed - current_speed) * 0.5

        # 推进物理世界（必须先做，感知依赖最新车辆位置）
        world.step(acc, steer)
        vehicle_state = world.vehicle.get_state()
        current_speed = vehicle_state["speed"]

        # ---------- 5.3 感知模块全链路更新（新增） ----------
        # 1. 激光雷达检测
        lidar.step(
            ego_x=vehicle_state["x"],
            ego_y=vehicle_state["y"],
            ego_yaw=vehicle_state["yaw"],
            true_obstacles=world.obstacles
        )
        # 2. 摄像头检测
        camera.step(
            ego_x=vehicle_state["x"],
            ego_y=vehicle_state["y"],
            ego_yaw=vehicle_state["yaw"],
            true_obstacles=world.obstacles
        )
        # 3. 多传感器融合
        perception_fusion.fuse(lidar.get_results(), camera.get_results())
        fused_obstacles = perception_fusion.get_results()

        # 4. 发布感知结果到全局事件总线，供下游模块订阅
        event_bus.publish(
            topic="perception_update",
            data={
                "timestamp": sim_time,
                "obstacles": [obs.to_dict() for obs in fused_obstacles]
            }
        )

        # ---------- 5.4 状态机条件跳转判断 ----------
        if state_machine.get_state() == STATE_STANDBY:
            if current_speed >= ACTIVE_LOW_SPEED_THRESHOLD:
                state_machine.transit(EV_ACTIVATE, vehicle_speed=current_speed)

        # ---------- 5.5 状态机时序更新 ----------
        state_machine.step(DT)

        # ---------- 5.6 控制台状态打印 ----------
        highest_alert = hmi.get_highest_level()
        # 统计感知结果分类
        fusion_count = sum(1 for o in fused_obstacles if o.source == "fusion")
        lidar_only = sum(1 for o in fused_obstacles if o.source == "lidar_only")
        camera_only = sum(1 for o in fused_obstacles if o.source == "camera_only")

        print(
            f"[t={sim_time:5.2f}s] "
            f"状态:{state_machine.get_state():<10} | "
            f"车速:{current_speed:5.2f} m/s | "
            f"位置:({vehicle_state['x']:6.2f}, {vehicle_state['y']:5.2f}) | "
            f"感知:共{len(fused_obstacles)}个(融合{fusion_count}/激光{lidar_only}/视觉{camera_only}) | "
            f"告警:{highest_alert}"
        )

        sim_time += DT

    # ===================== 6. 仿真结束输出 =====================
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


if __name__ == "__main__":
    main()