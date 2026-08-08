# 2026-08-01 日开发总览（收工）

> 明天续作请先读本文 + 根目录 `HANDOFF.md`。

## 完成事项

### 1. Map 模块

- `Link` / `Route` / `MapManager`：路线下发、waypoints 拼接、弧长投影限速与前方最低限速。
- `TrajPlanner.plan(..., speed_limit=)`：纵向基准速随限速缩放。
- 文档：`SUMMARY_2026-08-01_map.md`。

### 2. Web 实时渲染与场景配置

- `SimSession` + `SceneConfig`：从 `main._run_episode` 抽离；snapshot JSON。
- FastAPI：`/api/scene`、`/api/control`、`/api/presets`、`WS /ws/sim`。
- React（Vite）Canvas 鸟瞰 + 配置面板；中文 UI；预设：
  - `urban_turns`：主路 → 右转辅路 → 辅路 → 左转汇入 → 主路
  - `simple`：近直线三段
- 一键：`python3 run_web.py` / `./run_web.sh`（自动切到项目 `.venv`，避免系统 Python 缺 `uvicorn`）。
- 文档：`SUMMARY_2026-08-01_web_viz.md`。

### 3. Simulator / World 几何

- `LANE_WIDTH = 3.2` m；参考路径 = 车道中心线。
- `VEHICLE_WIDTH = 1.96` m（由 2.5 调回合理宽度），`VEHICLE_LENGTH = 4.8` m；状态 `(x,y)` = **后轴中心**。
- 单侧相对车道余量约 **0.62 m**。
- `simulator/geometry.py`：车道左右边界、后轴系车体矩形。
- Snapshot 增加 `lane_left` / `lane_right` / `vehicle_geom`；Web/matplotlib 同步绘制。
- 文档：`SUMMARY_2026-08-01_simulator.md`。

## 验证状态（收工时）

- `pytest`：**94 passed**（含车宽 1.96）
- Web：`./run_web.sh` 本地已跑通；`web/dist` 已 build（gitignore）

## 关键路径速查

| 用途 | 路径 |
|------|------|
| 一键 Web | `run_web.py` |
| 仿真会话 | `sim_server/session.py` |
| 场景/预设 | `sim_server/scene_schema.py` |
| 车道/车体常量 | `simulator/config.py` |
| 几何工具 | `simulator/geometry.py` |
| 地图 | `map/` |
| 前端 | `web/src/` |

## 明天建议起点

见 `HANDOFF.md` §6：优先世界场景与 3.2m 车道一致性，再打磨 control / planning。
