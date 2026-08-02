# AutoSim 交接文档（HANDOFF）

> 目的：让后续会话（人或 Agent）不依赖聊天上下文，即可从当前状态继续开发。  
> 最后更新：2026-08-02（午间续作）  
> 项目路径：`/Users/ricka/PycharmProjects/PythonProject`  
> 远程：`git@github.com:Yangle188/auto_sim_python.git`（`main`）

---

## 1. 一句话现状

主链路可用：Map 路线 → SimSession → Web 实时鸟瞰。已具备 **ACC**、**三车道道路朝上鸟瞰**、**反画龙 PP**、**Web 画布编路线/放障碍**、**底图起终点算路并下发 Route**。默认场景 `acc_highway`。`pytest`：**113 passed**。

**注意**：本轮 Web UX + base map 改动可能尚未 commit/push，开工先 `git status`。

---

## 2. 本轮完成（2026-08-02 续）

| 项 | 说明 | 状态 |
|----|------|------|
| Web 编路线 | 工具「编路线」：全图鸟瞰；点选追加/插入路点；拖拽；Delete 删末点 | ✅ |
| Web 放障碍 | 工具「放障碍」：点击放置；拖拽；Delete；动态只留 vx/vy | ✅ |
| 面板收敛 | 坐标文本默认隐藏；预设 + JSON 导入/导出 | ✅ |
| 底图 | `BaseMap` + 校园 3×3 网格 `campus_grid` | ✅ |
| 算路 | Dijkstra → `Route`；`GET /api/basemap`、`POST /api/route/plan` | ✅ |
| Web 算路 | 工具「算路」：点选起终点节点 → 写 draft → 应用并重开跟线 | ✅ |

此前（已 push）：ACC / 三车道 / PP / EKF 不拧 yaw 等，见 `git log`。

---

## 3. 环境与验证

```bash
cd /Users/ricka/PycharmProjects/PythonProject
source .venv/bin/activate
pytest
python run_web.py --rebuild   # 前端有改动时（npm 在 ~/.local/node/bin）
# 端口占用：lsof -ti:8000 | xargs kill -9
```

**约定旋钮**

| 文件 | 内容 |
|------|------|
| `simulator/config.py` | 车道 3.2 / `NUM_LANES=3` / 车宽 1.96 / 后轴 |
| `planning/config.py` | ACC：`TIME_GAP` / `MIN_GAP` / `FOLLOW_KP` |
| `control/config.py` | \(L_d(v)\)、`MAX_STEER_RATE` |
| `localization/config.py` | `GPS_STD_XY` 等 |
| `visualize/config.py` | CLI `HEADING_UP` |
| `map/demo_base_map.py` | 教学底图几何 |

---

## 4. 模块完成度

| 模块 | 状态 | 入口 |
|------|------|------|
| framework / simulator / perception / hmi | ✅ | 既有 |
| control | ✅ 反画龙 PP | `control/pure_pursuit.py` |
| planning | ✅ ACC | `planning/traj_planner.py` |
| localization | ✅ GPS 不拧 yaw | `localization/ekf_localizer.py` |
| map | ✅ 路线 + **底图算路** | `map/base_map.py`、`router.py` |
| sim_server + web | ✅ 画布编辑 + 算路 | `run_web.py`、`web/src/` |

---

## 5. 主循环数据流

```
SceneConfig（route links / obstacles / ScriptedMotion）
  → SimSession.step_once
      → MapManager(waypoints, speed_limit)
      → 感知(真值) → Predictor
      → TrajPlanner(est, ACC leads=动态障碍真值)
      → PurePursuit(true_pose, path) → world.step
      → EKF(predict; GPS 只修 x/y)
      → snapshot(lane_markings, acc, …)
  → Web（路径朝上 + 缩放）或 matplotlib

底图算路（编辑态）:
  BaseMap → 点选起终点 → POST /api/route/plan → draft SceneConfig
  → 应用并重开 → 同上主循环
```

**约定**

- 参考路径 = 自车车道中心线；VIS 画三车道标线  
- `(x,y)` = 后轴中心  
- 控制横向 = **真值**；规划/状态机 = EKF；估计青点仅显示  
- 场景：面板改 draft → **应用并重开**（非运行中热改拓扑）

---

## 6. 下一步优先

1. **算路体验**：底图边高亮、多底图切换、保留障碍选项、转弯 maneuver 推断  
2. **Web 打磨**：运行中提示「编辑将离开跟随视角」；脚本障碍简易关键帧编辑  
3. （可选）自车主动换道 / 完整 IDM  

未做（刻意延后）：运行中热改拓扑、多客户端、WebGL 3D。

---

## 7. 回归检查清单

- [x] `pytest`（113 passed）  
- [x] `web` `npm run build` 通过  
- [ ] 手动：`run_web.py --rebuild` → 算路 N7→N3 → 应用并重开跟线  
- [ ] 手动：编路线拖点、放障碍、JSON 导出再导入  
- [ ] 预设 ACC / 城市左右转仍可用  

---

## 8. 相关文档

| 文档 | 内容 |
|------|------|
| `docs/SUMMARY_2026-08-02_daily.md` | 08-02 收工总览（已部分过时，以本文件为准） |
| `docs/SUMMARY_2026-08-01_acc_viz.md` | ACC / 三车道 / 视角 |
| `docs/SUMMARY_2026-08-01_map.md` | 既有 map（限速路线） |
| `docs/SUMMARY_2026-08-01_web_viz.md` | Web / SceneConfig |
| `CHANGELOG.md` | 面向用户变更 |
| `README.md` | 入门启动 |

---

## 9. 给后续 Agent 的最短指令

> 先读 `HANDOFF.md` §6。本轮已完成 Web 画布编辑 + 校园底图算路。  
> 仿真：`python run_web.py --rebuild`。几何只动 `simulator/config.py`。  
> 改完 `pytest`；勿擅自 commit/push（除非用户要求）。
