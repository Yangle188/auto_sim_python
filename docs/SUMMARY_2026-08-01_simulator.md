# Simulator / World 几何（2026-08-01）

## 目标

- 实际车道宽度 **3.2 m**
- 自车宽度 **1.96 m**（长度 4.8 m）
- 状态点为**后轴中心**，应落在**车道中心线**上

## 常量（`simulator/config.py`）

| 常量 | 值 | 含义 |
|------|-----|------|
| `LANE_WIDTH` | 3.2 m | 单车道宽；中心线±1.6 m 为边界 |
| `VEHICLE_WIDTH` | 1.96 m | 车宽（两侧相对 3.2 m 车道约 0.62 m 余量） |
| `VEHICLE_LENGTH` | 4.8 m | 车长 |
| `WHEEL_BASE` | 2.7 m | 轴距（运动学） |
| `REAR_OVERHANG` | 1.0 m | 后轴→车尾 |

## API

- `simulator/geometry.py`
  - `lane_boundaries(centerline)` → `left` / `right` / `center`
  - `ego_footprint_world(x, y, yaw)` → 后轴系车体矩形角点
- `SimulationWorld`
  - `reference_path` = 车道中心线
  - `get_lane_boundaries()` / `get_vehicle_geom()`
- `Vehicle.get_state()` 含 `ref_point: "rear_axle"`

## 可视化

- Snapshot：`lane_left`、`lane_right`、`lane_width`、`vehicle_geom`
- matplotlib / Web：灰线车道边界；橙色车体矩形；十字 = 后轴

## 测试

```bash
pytest tests/test_world_geometry.py
```

## 注意

后续规划/控制若做横向约束或绕障，必须以车宽 1.96 与车道 3.2 为硬约束；当前 Pure Pursuit 仍主要贴中心线。
