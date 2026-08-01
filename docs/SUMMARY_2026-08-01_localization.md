# 开发总结：Localization 模块（2026-08-01）

本文记录 **localization（自行车模型 EKF）** 的原理、接口与接线。

---

## 1. 今日做了什么

### 1.1 背景

此前 planning / control 直接吃仿真真值位姿。实车上控制器只能看到估计位姿。本模块补上 EKF 定位闭环。

### 1.2 交付物

| 文件 | 作用 |
|------|------|
| `localization/config.py` | GPS 周期/噪声、过程噪声、初值协方差 |
| `localization/ekf_localizer.py` | 4 状态 EKF + 纯 Python 矩阵 |
| `main.py` | 感知用真值；规划/控制/状态机用估计；step 后 predict+GPS |
| `visualize/renderer.py` | 真值车体 + 青色虚线估计车体/轨迹；HUD `loc_err` |
| `tests/test_localization.py` | 预测一致性、GPS 降误差、航向 wrap |

### 1.3 范围边界

- **做了**：里程计预测 + GPS 位置更新
- **未做**：UKF、IMU 紧耦合、地图匹配、速度/航向直接观测

---

## 2. 状态与方程

状态 \(\mathbf{x}=[x,\,y,\,\psi,\,v]^\top\)。

**预测（欧拉，便于雅可比）：**

\[
\begin{aligned}
x &\leftarrow x + v\cos\psi\,\Delta t \\
y &\leftarrow y + v\sin\psi\,\Delta t \\
\psi &\leftarrow \psi + \frac{v}{L}\tan\delta\,\Delta t \\
v &\leftarrow \mathrm{clip}(v + a\,\Delta t)
\end{aligned}
\]

\(L=\) `WHEEL_BASE`。注意：与 `Vehicle.step` 的平均速度积分略有模型差，属有意简化，靠 GPS 修正。

**更新：** \(z=[x_{\mathrm{gps}},y_{\mathrm{gps}}]\)，\(H\) 只取位置两行。  
实现上把卡尔曼增益的速度行置零：位置残差不直接改 \(v\)（\(v\) 只由 `predict(acc)` 传播），减轻 ACTIVE/STANDBY 抖动。  
`main` 在 `v_cmd≈0`（越过终点）时强制 `steer=0`，避免终点外甩尾。

---

## 3. 主循环接线

```
true_state → 感知
est_state  → planning / control / 预瞄 / 状态机车速
world.step(acc, steer)
localizer.predict(acc, steer)
每 GPS_PERIOD：simulate_gps(true) → update_gps
visualize(true + est)
```

---

## 4. 接口

```python
from localization.ekf_localizer import EKFLocalizer

loc = EKFLocalizer()
loc.reset(x=0, y=0, yaw=0, speed=0)
loc.predict(acc, steer, dt=DT)
gx, gy = loc.simulate_gps(true_state)
loc.update_gps(gx, gy)
est = loc.get_state()  # {x,y,yaw,speed}
```

---

## 5. 参数一览

| 常量 | 默认 | 含义 |
|------|------|------|
| `GPS_PERIOD` | 0.1 s | GPS 更新周期 |
| `GPS_STD_XY` | 0.5 m | 位置观测噪声 |
| `PROCESS_VAR_*` | 小对角 | 过程噪声 |
| `P0_VAR_*` | 中等对角 | 初始不确定度 |
| `GPS_RNG_SEED` | 0 | 可复现噪声 |

---

## 6. 参考阅读顺序

1. `localization/config.py`
2. `localization/ekf_localizer.py`
3. `main.py` 5.2–5.4 节
4. `tests/test_localization.py`
5. `simulator/vehicle.py`（真值动力学对照）
