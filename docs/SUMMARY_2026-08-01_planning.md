# 开发总结：Planning 模块（2026-08-01）

本文记录 **planning（路径密化 + 纵向调速）** 的开发内容、计算原理与关键算法实现。

---

## 1. 今日做了什么

### 1.1 背景

接入 planning 之前，`main.py` 手写稀疏 `set_reference_path([(0,0),(50,0),(100,2)])`，控制侧固定 `TARGET_SPEED`，无法按障碍/终点动态调速。

### 1.2 交付物

| 文件 | 作用 |
|------|------|
| `planning/config.py` | 密化分辨率、巡航速、障碍/终点减速参数 |
| `planning/path_planner.py` | 折线弧长线性插值密化 |
| `planning/traj_planner.py` | 瞬时 `target_speed`（障碍 + 终点） |
| `main.py` | 感知前移；STANDBY/ACTIVE 使用密化路径；ACTIVE 传 `target_speed` |
| `tests/test_planning.py` | 路径密化与纵向调速单测 |
| `HANDOFF.md` / `README.md` | 状态同步 |

### 1.3 范围边界

- **做了**：密化路径 + 标量速度指令
- **未做**：几何绕障 / A* / 完整时空轨迹（留给后续 + prediction）

---

## 2. 计算原理

### 2.1 在栈中的位置

```
稀疏航点 ──► PathPlanner ──► 密化路径 ──► PurePursuit（横向）
融合障碍 + 自车位姿 ──► TrajPlanner ──► target_speed ──► PurePursuit（纵向）
```

保持 `PurePursuit.compute(vehicle_state, path, target_speed=...)` 接口不变。

### 2.2 PathPlanner：折线密化

对相邻航点 \(P_i \to P_{i+1}\)，段长 \(L\)，分辨率 \(\Delta s\)：

\[
n = \max\bigl(1,\,\lfloor L / \Delta s \rfloor\bigr),\quad
t_k = \frac{k\,\Delta s}{L},\quad k=1,\ldots,n\ (t_k < 1)
\]

插值点 \(P(t) = (1-t)P_i + t\,P_{i+1}\)，并保留每段终点。默认 \(\Delta s = 2\,\mathrm{m}\)。

### 2.3 TrajPlanner：瞬时目标车速

1. 找路径最近点下标 `closest_idx`
2. 剩余弧长 \(s_{\mathrm{remain}}\)：车 → 最近点 → 终点
3. 前方挡路障碍：横向距路径 \(<\) `OBSTACLE_LATERAL_CLEARANCE`，且 `obs_idx >= closest_idx`，取最近纵向距离 \(d_{\mathrm{obs}}\)
4. 速度取更保守者：

**障碍：**

- \(d \ge S_{\mathrm{slow}}\) → \(v_{\mathrm{cruise}}\)
- \(d \le S_{\mathrm{stop}}\) → \(0\)
- 其间：从 `MIN_SPEED` 线性插值到 `CRUISE_SPEED`

**终点：**

- 已越过终点（相对最后一段航向点积 > 0）→ \(s_{\mathrm{remain}} = 0\) → \(v = 0\)
- \(s_{\mathrm{remain}} \ge S_{\mathrm{end}}\) → \(v_{\mathrm{cruise}}\)
- 否则 \(v = v_{\mathrm{cruise}} \cdot s_{\mathrm{remain}} / S_{\mathrm{end}}\)

STANDBY 仅在 `v_cmd ≈ cruise` 时使用固定 `STANDBY_ACC`；接近终点/障碍时改跟规划速度，避免低速掉出 ACTIVE 后又被强制加速造成状态抖动。

---

## 3. 主循环时序

为让 ACTIVE 调速能读到当帧障碍，顺序调整为：

1. 感知（lidar / camera / fusion）
2. `path = PathPlanner.plan(waypoints)`
3. `v_cmd = TrajPlanner.plan(...)`（仅 ACTIVE）
4. `PurePursuit.compute` → `world.step`
5. 状态机车速条件判断

场景障碍放在路径旁侧（横向超出 clearance），避免演示中被刹停退出 ACTIVE；挡路减速行为由单测覆盖。

---

## 4. 参数一览

| 常量 | 默认值 | 含义 |
|------|--------|------|
| `PATH_RESOLUTION` | 2.0 m | 密化点间距 |
| `CRUISE_SPEED` | 10.0 m/s | 巡航（对齐 control） |
| `MIN_SPEED` | 1.0 m/s | 障碍减速区下限（未到停车） |
| `STOP_DISTANCE` | 5.0 m | 障碍停车距离 |
| `SLOW_DISTANCE` | 25.0 m | 障碍开始减速距离 |
| `OBSTACLE_LATERAL_CLEARANCE` | 3.0 m | 挡路横向阈值 |
| `END_SLOW_DISTANCE` | 15.0 m | 终点减速弧长 |

---

## 5. 参考阅读顺序

1. `planning/config.py`
2. `planning/path_planner.py`
3. `planning/traj_planner.py`
4. `main.py` 中 5.2 / 5.3 节
5. `tests/test_planning.py`
6. `control/pure_pursuit.py`（`target_speed` 消费端）
