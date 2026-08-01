# Map 模块开发总结（2026-08-01）

## 目标

支持**路线下发**：`Route = 有序 Link 列表`；自车横向跟 Route 几何，纵向按当前（及前方）link 限速行驶，并与障碍/预测/终点减速取更保守者。

## 新增 / 修改文件

| 文件 | 内容 |
|------|------|
| `map/config.py` | `SPEED_LOOKAHEAD_DIST`、衔接容差 |
| `map/link.py` | `Link(link_id, points, speed_limit)` |
| `map/route.py` | `Route` + 相邻端点衔接校验 |
| `map/map_manager.py` | 下发 / 拼接 / 限速查询 |
| `map/demo_routes.py` | 教学默认三段路线 |
| `planning/traj_planner.py` | `plan(..., speed_limit=)` 作纵向基准速 |
| `main.py` | 下发 demo route；限速接线 |
| `visualize/renderer.py` | link 分段着色 + HUD 限速 |
| `tests/test_map.py` | 下发、拼接、限速、规划 |

## 数据流

```
set_route → MapManager → waypoints → PathPlanner → dense path
                      → speed_limit_ahead → TrajPlanner → v_cmd
dense path + v_cmd → PurePursuit
```

## 演示路线

| Link | 几何 | 限速 |
|------|------|------|
| L1 | `(0,0)→(40,0)` | 8 m/s |
| L2 | `(40,0)→(70,1)` | 12 m/s |
| L3 | `(70,1)→(100,2)` | 6 m/s |

`get_speed_limit_ahead` 默认向前扫 20 m，取区间内最低限速，便于进入 L3 前提前降速。

## TrajPlanner

```python
v_base = cruise_speed if speed_limit is None else max(0.0, speed_limit)
v = min(v_base, speed_from_obstacle(..., v_base), speed_from_remaining(..., v_base))
```

障碍/终点减速曲线相对 `v_base` 缩放，避免限速 6 时仍按巡航 10 插值。

## 验证

```bash
pytest tests/test_map.py
pytest
ENABLE_VISUALIZE=False python main.py   # 或 visualize/config 关窗
```
