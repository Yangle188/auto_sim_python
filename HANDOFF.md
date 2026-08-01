# AutoSim 交接文档（HANDOFF）

> 目的：让后续会话（人或 Agent）不依赖聊天上下文，即可从当前状态继续开发。  
> 最后更新：2026-08-01（ACC + 三车道 heading-up）  
> 项目路径：`/Users/ricka/PycharmProjects/PythonProject`

---

## 1. 一句话现状

AutoSim 主链路已齐；**今日新增**：时距 ACC（跟车 / cut-in 减速 / cut-out 加速）、**三车道**标线、**车头向上**鸟瞰。默认场景为 `acc_highway`。`pytest`：**103 passed**。

---

## 2. 本轮完成（2026-08-01 续）

| 项 | 说明 |
|----|------|
| ACC | `TrajPlanner` 时距跟车；预测 cut-in 前瞻；无 lead 回限速 |
| 场景 | `acc_highway` + `ScriptedMotion` 关键帧剧本；默认预设 |
| 三车道 | `NUM_LANES=3`；`lane_markings` 实线路缘 + 虚线分隔 |
| 视角 | Web / matplotlib 均为 heading-up（车头向上） |
| 测试 | `tests/test_traj_acc.py` 等；103 passed |

日总结：`docs/SUMMARY_2026-08-01_acc_viz.md`。

---

## 3. 环境与验证

```bash
cd /Users/ricka/PycharmProjects/PythonProject
pytest
python run_web.py --rebuild   # 前端有改动时必须 rebuild
python main.py                # CLI 鸟瞰（heading-up）
```

**注意**

- `run_web.py` 若检测到项目 `.venv` 且当前不在其中，会 `exec` 切换后再启动。
- 端口占用：`lsof -ti:8000 | xargs kill -9`。
- 几何常量只改 `simulator/config.py`（车道 3.2 / 三车道 / 车宽 1.96 / 后轴）。
- ACC 参数：`planning/config.py`（`TIME_GAP` / `MIN_GAP` / `FOLLOW_KP`）。
- 关 CLI 车头向上：`visualize/config.py` → `HEADING_UP = False`。

---

## 4. 模块完成度

| 模块 | 状态 | 关键入口 |
|------|------|----------|
| framework / simulator / perception / hmi | ✅ | 既有 SUMMARY |
| control / localization / prediction / map | ✅ | 既有 SUMMARY |
| planning | ✅ ACC | `planning/traj_planner.py` |
| sim_server + web | ✅ | `run_web.py`；默认 `acc_highway` |
| visualize | ✅ heading-up | `visualize/renderer.py` |

---

## 5. 主循环数据流

```
SceneConfig（路线/障碍/ScriptedMotion）
  → SimSession.step_once
      → MapManager → 感知 → Predictor
      → TrajPlanner(ACC: lead/cutin/cutout, speed_limit)
      → PurePursuit → world.step → EKF
      → snapshot(+ lane_markings, num_lanes, acc, view)
  → WS/React 或 matplotlib（heading-up）
```

**约定**

- 参考路径 = **自车车道中心线**；VIS 画左右邻道
- 车辆状态 `(x,y)` = **后轴中心**
- 感知吃真值；规划/状态机吃 EKF 估计；**横向 Pure Pursuit 吃真值位姿**
- GPS 更新**不修正 yaw**（只修正 x/y），避免估计车体被噪声拧着「假画龙」
- 预瞄：路径弧长插值 + \(L_d(v)\) + 转角限速
- Web：相机朝向=路径切向；橙框=真值自车；青点=定位估计；可缩放
- 场景配置：面板改 draft → **应用并重开**

---

## 6. 下一步建议（按序）

1. **ACC 打磨**：IDM / 更稳的相对速度制动；前车外形用车长修正间距  
2. **Control**：预瞄 \(L_d(v)\)、段上插值  
3. **Planning**：曲率限速；几何绕障（换道）  
4. **Web UX**：画布点选加障碍；录帧  
5. **多车道规划**：可选左/右道中心线目标（目前仅 VIS 三车道）

未做（刻意）：运行中热改路线、多客户端、WebGL 3D、自车主动换道。

---

## 7. 回归检查清单

- [x] `pytest`（103 passed）  
- [ ] `python run_web.py --rebuild`：默认场景可见三车道、车头向上、ACC HUD  
- [ ] 观察：跟车降速 → 切出升速 → 切入再降速 → 再切出回限速  
- [ ] 预设切回「城市：左右转」仍可用  
- [ ] `ENABLE_VISUALIZE=False` 时 `python main.py` 可跑完  

---

## 8. 相关文档

| 文档 | 内容 |
|------|------|
| `docs/SUMMARY_2026-08-01_acc_viz.md` | **本轮 ACC / 三车道 / heading-up** |
| `docs/SUMMARY_2026-08-01_daily.md` | 此前收工总览 |
| `CHANGELOG.md` | 面向用户的变更摘要 |
| `README.md` | 入门与启动 |

---

## 9. 给后续 Agent 的最短指令

> 先读 `HANDOFF.md` 与 `docs/SUMMARY_2026-08-01_acc_viz.md`。  
> 默认场景 `acc_highway`；ACC 在 `TrajPlanner`；三车道在 `simulator/geometry.py`。  
> 前端改完：`python run_web.py --rebuild`。改完跑 `pytest`；勿擅自 commit。
