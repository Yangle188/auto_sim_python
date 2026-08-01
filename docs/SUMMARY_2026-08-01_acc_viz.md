# 2026-08-01 续：ACC 跟车 + 三车道车头向上可视化

## 目标

1. 自车纵向：跟车巡航、应对 cut-in 减速跟随、应对 cut-out 加速回目标车速  
2. 鸟瞰：单车道 → 三车道标线  
3. 视角：世界固定 → 车头向上（heading-up）

## 实现要点

### Planning（`TrajPlanner`）

- 时距 ACC：`d_des = MIN_GAP + TIME_GAP * v_ego`，`v = min(v_base, v_lead + FOLLOW_KP*(d-d_des))`
- 本车道横向阈值收紧为 ~1.8m（半车道级），邻道不误跟
- 预测轨切入本车道 → `source=cutin` 提前当 lead
- 前车离开本车道 → 无 lead，`v_cmd → speed_limit`（cut-out 加速）
- 参数：`planning/config.py`（`TIME_GAP` / `MIN_GAP` / `FOLLOW_KP`）
- 仿真会话把动态障碍真值速度作为 `leads=` 注入（避免感知噪声误跟）；无 leads 时仍可用 prediction

### 场景

- 新路线 `acc_highway`（直行走廊，限速 12）
- 新预设 / 默认场景：`acc_highway`（脚本关键帧：跟车 → 切出 → 切入 → 再切出）
- `ScriptedMotion`：关键帧插值；`LinearMotion` 仍兼容
- 城市 / 简易预设保留

### 几何 / Snapshot

- `NUM_LANES=3`；`multi_lane_boundaries`：外侧实线 + 车道虚线分隔
- snapshot：`num_lanes`、`lane_markings`、`acc`、`view.mode=heading_up`

### 可视化

- Web `BirdEyeCanvas`：自车中心、车头向上固定视野
- matplotlib：同为 heading-up（`visualize/config.py` 可关 `HEADING_UP`）

## 验证

```bash
pytest   # 103 passed
python run_web.py --rebuild
```

预设选「三车道：跟车 / Cut-in / Cut-out」，观察 HUD 的 ACC 行与目标车速变化。
