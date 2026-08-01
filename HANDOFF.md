# AutoSim 交接文档（HANDOFF）

> 目的：让后续会话（人或 Agent）不依赖聊天上下文，即可从当前状态继续开发。  
> 最后更新：2026-07-31  
> 项目路径：`/Users/ricka/PycharmProjects/PythonProject`

---

## 1. 一句话现状

模块化自动驾驶仿真原型（AutoSim）：状态机 + 事件总线 + 自行车模型 + 激光/视觉感知融合 + HMI + **Pure Pursuit 控制闭环** 已接通；`pytest` 全绿。下一优先可做 **planning**、**visualize** 或 **localization**。

---

## 2. 环境与验证

```bash
cd /Users/ricka/PycharmProjects/PythonProject
source .venv/bin/activate   # Python 3.14 已验证；需 3.10+
pip install -r requirements.txt   # 仅 pytest
pytest                          # 预期全部通过（2026-07-31：39 passed）
python main.py                  # 20s 仿真，含跟路径控制
```

- 运行时无第三方依赖；测试依赖 pytest。
- Git：分支 `main`，近期提交含 `add control module`。

---

## 3. 模块完成度

| 模块 | 状态 | 关键文件 |
|------|------|----------|
| `config/` | ✅ | `base_config.py`（DT、状态枚举、HMI 等级） |
| `framework/` | ✅ | `state_machine.py`、`event_bus.py`、`config.py` |
| `simulator/` | ✅ | `vehicle.py`（自行车模型）、`world.py`（障碍物+参考路径） |
| `perception/` | ✅ | lidar/camera sim + `perception_fusion.py` |
| `hmi/` | ✅ | `hmi_manager.py` |
| **`control/`** | ✅ **今日完成** | `config.py`、`pure_pursuit.py`；测试 `tests/test_control.py` |
| `localization/` | ❌ 空占位 | `ekf_localizer.py` |
| `prediction/` | ❌ 空占位 | `predictor.py` |
| `planning/` | ❌ 空占位 | `path_planner.py`、`traj_planner.py` |
| `visualize/` | ❌ 空占位 | `renderer.py` |

脚手架清单：`scaffold_config.json`（`skip_exist_file: true`）。空文件不要随便覆盖已有实现。

---

## 4. 架构与主循环约定

数据流（当前实际接线）：

```
状态机 ──► 是否输出控制
world.reference_path + vehicle_state ──► PurePursuit.compute ──► (acc, steer)
                                                              ──► world.step
true_obstacles + ego ──► lidar/camera ──► fusion ──► event_bus("perception_update")
state_change / hmi_alert ──► HMIManager
```

`main.py` 控制策略：

- **STANDBY**：横向用 `PurePursuit`；纵向固定 `STANDBY_ACC`（起步）。
- **ACTIVE**：`acc, steer = controller.compute(vehicle_state, world.reference_path)`。
- 其它状态：`acc=0, steer=0`。

时序事件：t≈0.5s 上电，t≈2.5s 自检；用 `sim_time + DT*0.5` 判断，避免浮点晚一拍。

配置分层（勿重复定义车辆物理上限）：

- 全局：`config/base_config.py`
- 状态机阈值：`framework/config.py`
- 车辆约束：`simulator/config.py`（轴距、转角/加减速度上限）
- 控制旋钮：`control/config.py`（预瞄距离、巡航速、Kp、STANDBY_ACC）

代码风格：模块内 `config.py` + 类；类型提示；控制/传感器输出限幅；测试风格对齐 `tests/test_vehicle.py`（可 `pytest` 也可 `__main__` 跑）。

---

## 5. Control 接口（已冻结，后续模块应对接）

```python
from control.pure_pursuit import PurePursuit

ctrl = PurePursuit()  # 可选覆盖 lookahead / target_speed / speed_kp / wheel_base
acc, steer = ctrl.compute(
    vehicle_state,          # dict: x, y, yaw, speed
    path,                   # List[Tuple[x,y]]，现为 world.reference_path
    target_speed=None,      # None → 用 ctrl.target_speed；留给 planning 动态调速
)
# 输出已按 MAX_ACC / MAX_DECEL / MAX_STEER_ANGLE 限幅
```

预瞄点算法要点（踩过坑）：**不能**简单取「全局第一个距离 ≥ Ld 的点」，否则驶离起点后会选中身后点。正确做法：先找最近路点索引，再从 `closest_idx+1` 向前找。详见 `docs/SUMMARY_2026-07-31_control.md`。

已知局限（有意留到后续）：

- 路径点稀疏（main 里仅 3 点）；无折线插值、无随速变 Ld。
- 纵向仅为 P 控制；动态调速接口已留，策略未做。
- 无障碍物避障/跟车（需 planning + prediction）。

---

## 6. 建议的下一任务（按优先级任选）

1. **planning**：用规划输出替换手写 `set_reference_path`；向 `compute(..., target_speed=...)` 喂速度曲线。
2. **visualize**：渲染车辆、路径、预瞄点、障碍物（便于调 Ld / 路径）。
3. **localization**：EKF，主循环用估计位姿喂控制（现为真值）。
4. **prediction**：动态障碍轨迹，供规划减速。
5. **打磨 control**：路径段插值预瞄、\(L_d(v)\)、STANDBY/ACTIVE 策略细化。
6. **文档同步**：更新根目录 `README.md`（仍写着 control 未实现）；`scaffold_config.json` 可补上 `tests/test_control.py`。

教学式开发偏好（若用户再次要求）：先原理 → 再骨架 → 再实现 → 再接线/测试；用户也可能直接说「直接实现」。

---

## 7. 回归检查清单（改完必跑）

- [ ] `pytest`
- [ ] `python main.py` 能完整跑完；ACTIVE 后车应沿参考路径前进，末端附近 y 向 `(100,2)` 靠拢
- [ ] 不在 `control` 里复制 `WHEEL_BASE` / 限幅常量
- [ ] 融合层勿原地改写传感器结果的 `source`（历史 bug）
- [ ] 状态机自检失败/超时须拦住进 STANDBY（历史 bug）

---

## 8. 相关文档

| 文档 | 内容 |
|------|------|
| `docs/SUMMARY_2026-07-31_control.md` | 今日 control 开发总结、计算原理、算法实现 |
| `README.md` | 入门说明（部分「规划中模块」表述可能滞后，以本文为准） |
| `scaffold_config.json` | 目标目录树 |

---

## 9. 给后续 Agent 的最短指令

> 阅读 `HANDOFF.md` 与 `docs/SUMMARY_2026-07-31_control.md`。在 `PythonProject` 下继续未实现模块（优先 planning 或 visualize）。保持现有 `PurePursuit.compute` 接口；动态速度经 `target_speed` 传入。改完跑 `pytest` 与 `python main.py`。
