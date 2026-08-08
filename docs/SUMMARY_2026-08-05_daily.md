# 2026-08-05 收工总览

> L2 Phase 1 落地 + 晚间 UX 打磨。细则变更见根目录 `CHANGELOG.md`；继续开发先读 `HANDOFF.md`。

## 今日结论

主链路可教学演示 **LCC 居中 → 拨杆变道 → ACC → FCW/AEB**。  
默认预设 `highway_lcc`；另有 `highway_aeb`、`urban_arterial`。  
`pytest`：**133 passed**（编写本文时）。

## 已落地（可演示）

### 功能（P1）

1. **LaneMap**（`map/lane_map.py`）：车道中心线、虚实线、左右邻道、successor；中心线 adapter  
2. **教学底图**：`highway_3lane`、`urban_arterial`；`campus_grid` 仍可算路  
3. **LCC**：Session 跟 `ego_lane` 中心线链  
4. **拨杆变道**：`planning/lane_change.py`；Web「左/右变道」与 `[` / `]`  
5. **FCW / AEB**：`safety/aeb.py`，与 ACC 纵向仲裁  

### 晚间 UX / 观感

6. **事件日志**：`SimSession._sim_log` → HMI「事件日志」  
7. **鸟瞰左右**：车体左侧映射到屏幕左侧（修正左右变道观感相反）  
8. **变道视角**：`view.cam_yaw` 锁定道路/车道切向，换道时画面不拧；自车仍可横向移动  
9. **加速度 HUD**：snapshot `accel`（m/s²），鸟瞰左上角显示  
10. **HMI 窗口**：标题栏可拖动；事件日志可滚动，避免底部裁切  

## 文档索引（今日相关）

| 文档 | 内容 |
|------|------|
| [SUMMARY_2026-08-05_l2_p1.md](SUMMARY_2026-08-05_l2_p1.md) | LaneMap / LCC / 变道 / AEB 专题 |
| [auto_sim_learning.md](auto_sim_learning.md) | 学习手册（含 §17.3 LCC/变道/AEB） |
| [../HANDOFF.md](../HANDOFF.md) | 交接与 P2–P5 |
| [../CHANGELOG.md](../CHANGELOG.md) | 面向用户的变更列表 |
| [../README.md](../README.md) | 快速开始与模块总览 |

## 关键文件

| 路径 | 备注 |
|------|------|
| `map/lane_map.py` / `map/demo_lane_maps.py` | 车道级底图 |
| `planning/lane_change.py` | 拨杆变道状态机 |
| `safety/aeb.py` | FCW / AEB |
| `sim_server/session.py` / `scene_schema.py` | LCC 绑定、仲裁、snapshot、`_sim_log` |
| `web/src/BirdEyeCanvas.tsx` | 道路朝上相机、加速度 HUD、左右映射 |
| `web/src/HmiPanel.tsx` / `styles.css` | 可拖动 HMI + 可滚动日志 |
| `tests/test_lane_map.py` / `test_lane_change.py` / `test_aeb.py` | 新增单测 |

## 启动与演示

```bash
cd /Users/ricka/PycharmProjects/PythonProject
source .venv/bin/activate
pytest
python3 run_web.py --rebuild
```

1. **LCC + 变道**：预设「高速：LCC + 拨杆变道」→ 开始 → 待机后激活 → 左变道超越右道静止车；实线段拨杆应拒绝。  
2. **AEB**：预设「高速：FCW / AEB」→ 激活接近静止前车 → HMI 先 FCW 再 AEB。  
3. **HMI**：拖标题栏移动窗口；日志区滚动查看完整事件。

## 下一步（摘要）

见 `HANDOFF.md` P2–P5：告警自动消失、OVERRIDE/TOR、路口拼接、感知闭环 ACC 等。
