# AutoSim 交接文档（HANDOFF）

> 目的：让后续会话（人或 Agent）不依赖聊天上下文，即可从当前状态继续开发。  
> 最后更新：2026-08-05（L2 P1 + 鸟瞰/HMI UX 打磨）  
> 项目路径：`/Users/ricka/PycharmProjects/PythonProject`  
> 远程：`git@github.com:Yangle188/auto_sim_python.git`（`main`）

---

## 1. 一句话现状

主链路可演示 **教学 L2**：车道级底图 → LCC 居中 → **拨杆变道** → ACC → **FCW/AEB**。默认场景 `highway_lcc`（右道起步 + 前方静止障）。另有 `highway_aeb`、`urban_arterial`、原 ACC cut-in 等预设。  
Web：道路朝上鸟瞰（变道不拧画面）、加速度 HUD、可拖动 HMI 事件日志。

---

## 2. 本轮完成（P1 + UX）

| 项 | 说明 |
|----|------|
| LaneMap | `map/lane_map.py`：Lane / 邻接 / 虚实线 / successor；中心线 adapter |
| 底图 | `highway_3lane`、`urban_arterial`；`campus_grid` 仍可算路 |
| LCC | Session 跟 `ego_lane` 中心线链；snapshot 含 `ego_lane_id` / `lane_index` |
| 拨杆变道 | `planning/lane_change.py`；API `lane_change` + Web「左/右变道」+ `[` / `]` |
| FCW/AEB | `safety/aeb.py`；盖写纵向；HMI「请注意前方」/「自动紧急制动」 |
| 预设 | `highway_lcc`（默认）、`highway_aeb`、`urban_arterial` 等 |
| 事件日志 | `_sim_log` → HMI「事件日志」 |
| 鸟瞰左右 | 车体左 = 屏幕左（修正变道方向观感） |
| 变道视角 | `view.cam_yaw` 锁道路切向，不跟过渡曲线 |
| 加速度 | snapshot `accel`；HUD 显示 m/s²（`acc` 仍是跟车信息） |
| HMI 窗 | 标题栏拖动；日志可滚动 |

---

## 3. 环境与验证

```bash
cd /Users/ricka/PycharmProjects/PythonProject
source .venv/bin/activate
pytest          # 约 133 passed
python run_web.py --rebuild
# 端口占用：lsof -ti:8000 | xargs kill -9
```

**LCC + 变道：** 预设「高速：LCC + 拨杆变道」→ 开始 → 待机后激活 → 达速后「左变道」超越右道静止车；驶入实线段再拨杆应提示无法变道。变道时自车横向移动、画面 heading 应保持道路朝上。

**AEB：** 预设「高速：FCW / AEB」→ 激活后接近静止前车 → HMI 先 FCW 再 AEB，不碰撞。

**HMI：** 拖标题栏移动；滚轮/拖动滚动条查看完整事件日志。

---

## 4. 下一步建议（P2–P5）

### P2 驾驶员责任
1. 告警自动消失（`ALERT_AUTO_CLEAR_S`）+ HMI 优先级  
2. OVERRIDE 演示入口 + 接管请求 TOR  

### P3 场景打磨
3. 路口车道线拼接；转弯 auto-maneuver  
4. 脚本障碍关键帧编辑器；draft≠applied 角标  

### P4 感知闭环教学
5. 感知驱动 ACC 开关（关掉 `_truth_leads`）  
6. 横向可选估计位姿  

### P5 L2+ 选修
7. 简单绕障 nudge；DMS / hands-off 计时  

---

## 5. 文档

| 文档 | 用途 |
|------|------|
| [docs/auto_sim_learning.md](docs/auto_sim_learning.md) | **学习手册** |
| [docs/SUMMARY_2026-08-05_daily.md](docs/SUMMARY_2026-08-05_daily.md) | 本日收工总览 |
| [docs/SUMMARY_2026-08-05_l2_p1.md](docs/SUMMARY_2026-08-05_l2_p1.md) | L2 P1 专题 |
| [README.md](README.md) | 快速开始、模块总览 |
| [CHANGELOG.md](CHANGELOG.md) | 变更列表 |

## 6. 给后续 Agent

> 先读 §4。仿真：`python run_web.py --rebuild`（改 Python 后必须重启进程）。几何只动 `simulator/config.py`；车道图在 `map/demo_lane_maps.py` / `map/lane_map.py`。  
> **事件日志**：关键功能/场景变化用 `SimSession._sim_log(code, msg)` 写入 HMI 面板（勿 silent）。  
> **鸟瞰**：相机用 `view.cam_yaw` / 车道中心线，勿用变道 `path` 切向；车体左 = +y = 屏幕左。  
> **字段**：`accel` = 纵向加速度指令；`acc` = ACC 跟车 `{d_gap,v_lead,source}`。  
> 改完 `pytest`；勿擅自 commit/push（除非用户要求）。
