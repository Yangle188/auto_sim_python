# Changelog

本文件记录 AutoSim（`PythonProject`）面向用户的变更摘要。

## 2026-08-01

### Map

- 新增路线下发：`Link` / `Route` / `MapManager`；演示三段不同限速路线。
- `get_speed_limit` / `get_speed_limit_ahead` 供纵向规划；`TrajPlanner.plan(..., speed_limit=)` 以限速为基准速。
- `main` 用 demo route 替代手写三点路径；鸟瞰按 link 限速着色并显示 HUD `limit`。

### Visualize

- **仿真中可暂停**：交互窗口下按 `Space` 暂停/继续；暂停期间仿真主循环阻塞，窗口标题与 HUD 显示 `PAUSED`。
- **结束后保持界面**：仿真跑完后默认不立刻关闭鸟瞰窗；关闭窗口或按 `q` / `Esc` 再退出。可用 `visualize/config.py` 中 `HOLD_ON_FINISH = False` 关闭该行为。
- **重复播放**：窗口右下角 `Replay` 按钮（或按 `r`）可重跑整段仿真；运行中 / 暂停中 / 结束后均可触发；重播清空轨迹并重置场景。
- 新增接口：`block_while_paused()`、`hold_until_closed()`（返回 `replay`/`close`）、`prepare_replay()`、`consume_replay_request()`（`NullRenderer` / Agg 为空操作，不影响无头与 pytest）。

### Prediction

- 新增恒速（CV）障碍预测：检测聚类、最近邻跟踪、短时外推。
- `TrajPlanner.plan(..., predictions=)` 支持前瞻减速；场景增加横向穿越动态障碍。
- 鸟瞰绘制紫色虚线预测轨迹。

### Localization

- 新增 4 状态自行车模型 EKF（里程计预测 + 含噪 GPS）。
- 规划/控制/状态机使用估计位姿；感知仍用真值；鸟瞰叠加估计轨迹。

### Planning

- 路径密化（`PathPlanner`）+ 纵向调速（`TrajPlanner`：障碍/终点/预测）。

### Control

- Pure Pursuit 横向跟踪 + 纵向 P 控制；公开 `get_lookahead_point` 供可视化。

### Docs / Tooling

- 交接文档 `HANDOFF.md`、各模块 `docs/SUMMARY_*.md`、`README.md`、`scaffold_config.json` 同步。
- 运行依赖：`matplotlib`（可视化）；核心仿真 / EKF / 预测仍无强制数值库。
