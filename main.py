# main.py
from config import DT, STATE_ACTIVE, STATE_STANDBY, STATE_PASSIVE, HMI_INFO
from framework.state_machine import (
    AutoDriveStateMachine,
    EV_POWER_ON,
    EV_SELF_CHECK_OK,
    EV_ACTIVATE
)
from framework.event_bus import EventBus
from simulator.world import SimulationWorld
from hmi.hmi_manager import HMIManager


def main():
    # ===================== 1. 初始化全局核心组件 =====================
    event_bus = EventBus()
    state_machine = AutoDriveStateMachine()
    world = SimulationWorld()
    hmi = HMIManager(event_bus)

    # ===================== 2. 建立模块间事件关联 =====================
    # 状态机状态变更时：发布事件总线消息 + 推送HMI提示
    def on_state_changed(old_state: str, new_state: str):
        # 向全局总线发布状态变更事件，供所有订阅者接收
        event_bus.publish(
            topic="state_change",
            data={"old_state": old_state, "new_state": new_state}
        )
        # 同步推送HMI信息提示
        event_bus.publish(
            topic="hmi_alert",
            data={"level": HMI_INFO, "msg": f"系统状态切换：{old_state} → {new_state}"}
        )

    # 挂载状态变更回调
    state_machine.state_change_callback = on_state_changed

    # ===================== 3. 仿真运行参数初始化 =====================
    sim_time = 0.0
    total_sim_time = 20.0  # 总仿真时长 20秒
    self_check_done = False
    ad_activated = False

    print("=" * 60)
    print("自动驾驶仿真系统启动")
    print("=" * 60)

    # ===================== 4. 仿真主循环 =====================
    while sim_time < total_sim_time:
        # ---------- 4.1 固定时序事件触发 ----------
        # 仿真启动 0.5s 后系统上电
        if sim_time >= 0.5 and state_machine.get_state() == "OFF":
            state_machine.transit(EV_POWER_ON, vehicle_speed=0)

        # 上电后 2s 自检完成，进入待机状态
        if sim_time >= 2.5 and not self_check_done and state_machine.get_state() == STATE_PASSIVE:
            state_machine.transit(EV_SELF_CHECK_OK, vehicle_speed=0)
            self_check_done = True

        # ---------- 4.2 计算控制量 + 物理世界步进 ----------
        acc = 0.0
        steer = 0.0
        current_speed = world.vehicle.speed

        if state_machine.get_state() == STATE_STANDBY and not ad_activated:
            # 待机阶段车辆自动加速，满足条件后激活自动驾驶
            acc = 2.0
        elif state_machine.get_state() == STATE_ACTIVE:
            # 激活后保持 10m/s 匀速行驶（简单比例速度控制）
            target_speed = 10.0
            acc = (target_speed - current_speed) * 0.5

        # 推进一帧物理世界
        world.step(acc, steer)
        current_speed = world.vehicle.speed  # 更新步进后的最新车速

        # ---------- 4.3 状态机条件跳转判断 ----------
        if state_machine.get_state() == STATE_STANDBY and not ad_activated:
            # 车速满足阈值时，自动激活自动驾驶
            if current_speed >= 3.0:
                state_machine.transit(EV_ACTIVATE, vehicle_speed=current_speed)
                ad_activated = True

        # ---------- 4.4 状态机时序更新 ----------
        state_machine.step(DT)

        # ---------- 4.5 控制台状态打印 ----------
        vehicle_state = world.vehicle.get_state()
        highest_alert = hmi.get_highest_level()
        print(
            f"[t={sim_time:5.2f}s] "
            f"状态:{state_machine.get_state():<10} | "
            f"车速:{current_speed:5.2f} m/s | "
            f"位置:({vehicle_state['x']:6.2f}, {vehicle_state['y']:5.2f}) | "
            f"最高告警:{highest_alert}"
        )

        # 更新仿真时间
        sim_time += DT

    # ===================== 5. 仿真结束输出 =====================
    print("=" * 60)
    print("仿真结束，当前活跃告警列表：")
    for idx, alert in enumerate(hmi.get_active_alerts()):
        print(f"  {idx+1}. [{alert['level']}] {alert['msg']}")
    print("=" * 60)


if __name__ == "__main__":
    main()