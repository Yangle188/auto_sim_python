# 开发总结：Prediction 模块（2026-08-01）

本文记录 **prediction（恒速障碍预测）** 的原理、接口与接线。

---

## 1. 今日做了什么

### 1.1 背景

Planning 原先只看融合障碍的**当前**位置。动态障碍切入路径时反应偏晚。Prediction 提供短时轨迹，供 TrajPlanner 前瞻减速。

### 1.2 交付物

| 文件 | 作用 |
|------|------|
| `prediction/config.py` | 时域、关联距离、coast、速度阈值 |
| `prediction/predictor.py` | `PredictedObstacle` + `ObstaclePredictor` |
| `planning/traj_planner.py` | `plan(..., predictions=())` |
| `main.py` | 动态穿越障碍 + predictor 接线 |
| `visualize/renderer.py` | 紫色虚线预测轨迹 |
| `tests/test_prediction.py` | 外推 / coast / 规划减速 |

### 1.3 范围边界

- **做了**：CV 外推 + 最近邻跟踪 + 规划前瞻
- **未做**：交互博弈、多模态、卡尔曼跟踪、神经网络

---

## 2. 算法

### 跟踪

1. 检测中心与航迹最近邻（`< MATCH_DIST`）  
2. 匹配：\(\Delta p/\Delta t\) 更新速度（一阶低通）  
3. 未匹配检测 → 新建；未匹配航迹 → CV coast，超 `MAX_COAST_FRAMES` 删除  

### 预测

\[
(x_k, y_k) = (x,y) + k\,\Delta t_{\mathrm{pred}}\,(v_x,v_y),\quad k=1..N
\]

\(|v| < MIN_SPEED_FOR_MOTION\) 或 `age < MIN_AGE_FOR_PRED` 或 coasting 时只输出当前点。  
输入检测先按 `DET_CLUSTER_DIST` 聚类，减轻多源重复建轨。

### 规划

\(d_{\mathrm{threat}}=\min(d_{\mathrm{obs}},\,d_{\mathrm{pred}})\)，再套原有障碍减速曲线。  
预测侧只扫 `trajectory[1:]`（未来点）；当前位置已由 `obstacles` 覆盖。

---

## 3. 主循环

```
更新动态障碍真值
真值 → 感知融合
predictions = predictor.step(fused, DT)
est → traj_planner.plan(..., predictions) → control
world.step → EKF → visualize(predictions)
```

动态障碍：\(x=60,\; y=-8+1.5\,t\)（约 \(t=5.3\,\mathrm{s}\) 过 \(y=0\)）。

---

## 4. 接口

```python
from prediction.predictor import ObstaclePredictor

pred = ObstaclePredictor()
predictions = pred.step(fused_obstacles, dt=DT)
v_cmd = traj_planner.plan(est, path, fused, predictions)
```

---

## 5. 参数

| 常量 | 默认 | 含义 |
|------|------|------|
| `PRED_HORIZON` | 10 | 外推步数 |
| `PRED_DT` | 0.2 s | 预测步长 |
| `MATCH_DIST` | 3.0 m | 关联阈值 |
| `MAX_COAST_FRAMES` | 5 | 丢失保留帧数 |
| `MIN_SPEED_FOR_MOTION` | 1.0 m/s | 静止判定（抑噪声） |
| `VEL_LP_ALPHA` | 0.4 | 速度低通 |
| `MIN_AGE_FOR_PRED` | 2 | 外推前最少确认帧 |
| `DET_CLUSTER_DIST` | 2.0 m | 输入检测聚类 |

---

## 6. 参考阅读

1. `prediction/config.py`  
2. `prediction/predictor.py`  
3. `planning/traj_planner.py`（`_nearest_front_prediction_distance`）  
4. `main.py` 5.2–5.4  
5. `tests/test_prediction.py`
