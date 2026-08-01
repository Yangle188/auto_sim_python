   # 开发总结：Visualize 模块（2026-08-01）

本文记录 **visualize（鸟瞰 2D 渲染）** 的实现要点与接线方式。

---

## 1. 今日做了什么

### 1.1 背景

调 Pure Pursuit 预瞄距离、密化路径与规划减速时，仅靠控制台数字不够直观。需要鸟瞰图同时看到车、路径、预瞄点与障碍。

### 1.2 交付物

| 文件 | 作用 |
|------|------|
| `visualize/config.py` | 开关、刷新间隔、图尺寸、轨迹长度等 |
| `visualize/renderer.py` | `Renderer` / `NullRenderer` / `create_renderer()` |
| `control/pure_pursuit.py` | 新增 `get_lookahead_point`（不改 `compute` 返回值） |
| `main.py` | step 后组 snapshot 并 `renderer.update` |
| `tests/test_visualize.py` | Agg 后端单测 |
| `requirements.txt` | 增加 `matplotlib` |

### 1.3 范围边界

- **做了**：matplotlib 鸟瞰实时刷新 + HUD；`Space` 暂停；结束后 `hold_until_closed`
- **未做**：3D、摄像头画面、录视频、pygame

---

## 2. 架构

```
perception → planning → control → world.step
                                    ↓
                         snapshot(dict) → Renderer.update
```

- `ENABLE_VISUALIZE=False` 或未安装 matplotlib → `NullRenderer`（空操作）
- 测试强制 `matplotlib.use("Agg")`，不依赖显示器；Agg 下不调用 `plt.pause`，避免挂起
- `create_renderer()` 动态读取 `visualize.config.ENABLE_VISUALIZE`，便于运行时/测试关闭

### 图层

| 图层 | 画法 |
|------|------|
| 稀疏航点 | 灰折线 + 方点 |
| 密化路径 | 蓝细线 |
| 预瞄点 | 品红星 |
| 真值障碍 | 棕矩形 |
| 融合检测 | 空心圆（按 source 着色） |
| 自车 | 朝向三角形 + 橙色轨迹 |
| HUD | t / state / speed / v_cmd / steer / pos |

---

## 3. 接口

```python
from visualize.renderer import create_renderer

renderer = create_renderer()
renderer.update({
    "t": sim_time,
    "state": "...",
    "vehicle": {"x", "y", "yaw", "speed"},
    "waypoints": [...],
    "path": [...],
    "lookahead": (x, y) | None,
    "obstacles": world.obstacles,
    "fused": fused_obstacles,
    "v_cmd": v_cmd,
    "steer": steer,
})
renderer.close()
```

预瞄点：

```python
lookahead = controller.get_lookahead_point(vehicle_state, path)
```

---

## 4. 参数一览

| 常量 | 默认 | 含义 |
|------|------|------|
| `ENABLE_VISUALIZE` | True | 总开关 |
| `FIG_SIZE` | (10, 6) | 图尺寸（英寸） |
| `UPDATE_EVERY_N` | 2 | 隔帧刷新 |
| `TRAIL_LENGTH` | 80 | 轨迹点数 |
| `PAUSE_SEC` | 0.001 | `plt.pause` |
| `VIEW_PADDING` | 8.0 m | 视野边距 |
| `HOLD_ON_FINISH` | True | 结束后保持窗口 |
| `PAUSE_POLL_SEC` | 0.05 | 暂停/保持时事件轮询 |

快捷键 / 按钮（交互后端）：

- `Space`：暂停/继续  
- `Replay` 按钮或 `r`：重播整段仿真  
- 结束后：`q` / `Esc` 或关窗退出  

无头跑 `main` 时可设 `ENABLE_VISUALIZE=False`，或 `MPLBACKEND=Agg`。

---

## 5. 参考阅读顺序

1. `visualize/config.py`
2. `visualize/renderer.py`
3. `main.py` 中 5.6 节
4. `tests/test_visualize.py`
