# 开发总结：Control 模块（2026-07-31）

本文记录当日 **control（Pure Pursuit）** 的开发内容、计算原理与关键算法实现，便于复习与后续扩展。

---

## 1. 今日做了什么

### 1.1 背景

接入 control 之前，`main.py` 在 STANDBY/ACTIVE 下只写死纵向加速度，`steer` 恒为 0，车无法跟踪 `world.reference_path`。

### 1.2 交付物

| 文件 | 作用 |
|------|------|
| `control/config.py` | 预瞄距离、默认巡航速、纵向 Kp、STANDBY 加速度 |
| `control/pure_pursuit.py` | Pure Pursuit 横向 + 速度 P 控制 |
| `main.py` | 初始化控制器并按状态机调用 |
| `tests/test_control.py` | 11 个单测（预瞄、转角符号、限幅、闭环跟踪等） |
| `HANDOFF.md` | 项目交接（另文） |

### 1.3 实现步骤（教学节奏）

1. **配置**：抽出控制旋钮，车辆物理上限仍用 `simulator.config`。
2. **类骨架**：`compute` / `_find_lookahead_point` / `_calc_steer` / `_calc_acc`；`target_speed` 参数预留动态调速。
3. **预瞄点**：路径上向前选取目标点（并修复「选中身后点」问题）。
4. **转角公式**：车体坐标 + Pure Pursuit 几何公式。
5. **接线 + 测试**：主循环接入；pytest 覆盖。

### 1.4 主循环策略

- **STANDBY**：横向 `PurePursuit`，纵向 `STANDBY_ACC`（快速起步以满足激活车速）。
- **ACTIVE**：完整 `compute` → `(acc, steer)` → `world.step`。

---

## 2. 计算原理

### 2.1 控制在栈中的位置

```
参考路径 / 未来规划轨迹
        ↓
   横向：转角 δ     纵向：加速度 a
        ↓
  自行车模型积分 (x, y, yaw, v)
```

车辆输入已固定（见 `simulator/vehicle.py`）：

- \(a\)：加速度 (m/s²)
- \(\delta\)：前轮转角 (rad)
- 轴距 \(L =\) `WHEEL_BASE`

### 2.2 纵向：速度比例控制

\[
a = K_p \,(v_{\mathrm{target}} - v)
\]

再裁剪到 \([a_{\min},\, a_{\max}]\)（`MAX_DECEL` / `MAX_ACC`）。

- \(v_{\mathrm{target}}\) 默认来自 `TARGET_SPEED`；也可每帧传入 `compute(..., target_speed=...)`。
- 今日不做跟车/弯道自动调速；接口先留口，策略留给 planning。

### 2.3 横向：Pure Pursuit 几何直觉

把路径前方一个「预瞄点」\(T\) 当作要追的目标。假设车以当前姿态沿**一段圆弧**开向 \(T\)，由几何关系反解所需前轮转角 \(\delta\)。

- 预瞄距离 \(L_d\) 越大：转向越柔、越滞后。
- \(L_d\) 越小：跟得紧、易抖。

本项目配置：`LOOKAHEAD_DISTANCE = 8.0` m（固定；未做随车速变化）。

### 2.4 坐标系

- **世界系**：路径点、车辆 `(x, y, yaw)`。
- **车体系**：原点在车辆、\(x_r\) 朝车头、\(y_r\) 朝左。

世界系相对向量转到车体：

\[
\begin{aligned}
dx &= t_x - x,\quad dy = t_y - y \\
x_r &= \cos\psi\, dx + \sin\psi\, dy \\
y_r &= -\sin\psi\, dx + \cos\psi\, dy
\end{aligned}
\]

预瞄角（车头与指向 \(T\) 的夹角）：

\[
\alpha = \operatorname{atan2}(y_r,\, x_r)
\]

实际预瞄距离（到目标点的距离）：

\[
L_d = \sqrt{x_r^2 + y_r^2}
\]

### 2.5 Pure Pursuit 转角公式

\[
\delta = \arctan\left(\frac{2 L \sin\alpha}{L_d}\right)
\]

代码中用等价形式（`ld > 0` 时与上式同）：

\[
\delta = \operatorname{atan2}\bigl(2 L \sin\alpha,\; L_d\bigr)
\]

再限幅到 \(\pm\) `MAX_STEER_ANGLE`。  
\(L_d \approx 0\) 时直接令 \(\delta = 0\)，避免数值问题。

符号约定（与本仿真车辆模型一致）：

- 目标在左侧 \(\Rightarrow y_r>0 \Rightarrow \alpha>0 \Rightarrow \delta>0\)（左转，yaw 增大）。

---

## 3. 关键算法实现原理

### 3.1 `compute` 总流程

```
path 为空? → (0, 0)
取 (x,y,yaw,speed)，确定 v_target
T ← _find_lookahead_point
δ ← _calc_steer(..., T)
a ← _calc_acc(speed, v_target)
限幅 (a, δ) 后返回
```

### 3.2 预瞄点选取（含踩坑与修正）

**错误做法（已废弃）：** 从路径起点扫描，返回第一个「到车距离 ≥ \(L_d\)」的点。

问题：车开到 \(x=10\) 后，起点 `(0,0)` 距离为 10，仍 ≥ 8，会被当成预瞄点 → 目标在车后方 → 转角发散。

**当前做法：**

1. 找与车辆欧氏距离最小的路点下标 `closest_idx`。
2. 从 `closest_idx + 1` 起向路径终点扫描，返回第一个距离 ≥ `lookahead` 的点。
3. 若没有，返回 `path[-1]`。

这样预瞄点始终在「最近点之后」的路径前方，适合当前稀疏折线路点。

**尚未做、以后可增强：**

- 在折线**线段上按弧长插值**精确落在 \(L_d\) 处；
- \(L_d = L_d(v)\)；
- 用航向过滤「前方半平面」点。

### 3.3 `_calc_steer`

1. \(T - P\) 转车体坐标 \((x_r, y_r)\)。  
2. \(\alpha = \operatorname{atan2}(y_r, x_r)\)，\(L_d = \mathrm{hypot}(x_r, y_r)\)。  
3. \(\delta = \operatorname{atan2}(2 L \sin\alpha,\, L_d)\)。

### 3.4 `_calc_acc`

\[
a = \texttt{speed\_kp} \times (v_{\mathrm{target}} - v)
\]

限幅在 `compute` 末尾统一做。

### 3.5 与仿真的闭环关系

`Vehicle.step` 使用运动学自行车模型（平均速度 + 平均航向积分）。控制输出的 \(\delta\) 通过

\[
\dot\psi = \frac{v}{L}\tan\delta
\]

改变航向，从而改变下一帧的 `(x,y)`，再进入下一帧的预瞄与转角计算，形成路径跟踪闭环。

---

## 4. 测试要点（`tests/test_control.py`）

| 用例意图 | 断言要点 |
|----------|----------|
| 空路径 | `(0,0)` |
| 预瞄选取 / 跳过身后点 / 终点回退 | 目标点坐标 |
| 正前方 / 左 / 右目标 | \(\delta \approx 0\) / \(>0\) / \(<0\) |
| 纵向 P、target_speed 覆盖 | 加速度数值与大小关系 |
| 限幅 | 不超出车辆约束 |
| 直线闭环 | 初始横向偏差经若干秒后 \(|y|\) 仍较小 |

---

## 5. 参数一览（当日默认）

| 常量 | 值 | 含义 |
|------|-----|------|
| `LOOKAHEAD_DISTANCE` | 8.0 m | 预瞄距离 |
| `TARGET_SPEED` | 10.0 m/s | 默认巡航 |
| `SPEED_KP` | 0.5 | 纵向 P 增益 |
| `STANDBY_ACC` | 2.0 m/s² | 待机起步加速度 |
| `WHEEL_BASE` | 2.7 m | 轴距（simulator） |

调参建议：跟踪抖 → 增大 Ld；跟弯慢 → 减小 Ld 或加密路径点；超调/加速过猛 → 减小 `SPEED_KP`。

---

## 6. 参考阅读顺序（复习）

1. `control/config.py`  
2. `control/pure_pursuit.py`  
3. `main.py` 中 5.2 节控制分支  
4. `tests/test_control.py`  
5. `simulator/vehicle.py`（控制量如何变成运动）
