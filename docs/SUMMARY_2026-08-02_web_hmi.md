# 2026-08-02：Web 操控 · 状态机手动激活 · HMI 文言

## 目标

1. Web 可演示完整教学闭环：编场景 / 底图算路 → 仿真 → 回看  
2. **STANDBY→ACTIVE 需驾驶员主动操作**（不再因车速自动切入）  
3. 前端 **HMI 窗口**展示功能状态，并在关键时刻出文言  

## 能力一览

| 能力 | 说明 |
|------|------|
| 画布工具 | 浏览 / 算路 / 编路线 / 放障碍 |
| 底图算路 | `campus_grid` + Dijkstra → `Route`；金黄高亮导航边 |
| 时间轴 | 按整段 `duration` 定标；可拖动 seek（仅已录帧） |
| 逐帧 | 上一帧 / 下一帧；← / →；最新帧再下一步=单步进 |
| 预瞄轨迹 | 粉虚线路径预瞄 + 粉实线 PP 圆弧 + 预瞄点 |
| 手动激活 | 顶栏「激活」；车速未就绪可挂起，达速后切入 |
| 功能退出 | 顶栏「退出」→ ACTIVE→STANDBY |
| HMI 窗口 | 左上角：功能状态 + 最新提示 + 日志 |

## 状态机（驾驶员操作）

时序仍为：`OFF → PASSIVE(t≈0.5) → STANDBY(t≈2.5)`。

| 操作 | API | 条件 |
|------|-----|------|
| 激活 | `POST /api/control` `{"action":"activate"}` | 当前 STANDBY；车速宜在 5–30 m/s（未达速则挂起） |
| 退出 | `POST /api/control` `{"action":"deactivate"}` | 当前 ACTIVE |

实现要点：

- `SimSession.request_activate` / `request_deactivate`
- 去掉「STANDBY 且车速≥阈值即自动 `EV_ACTIVATE`」
- `status` 含 `ad_state` / `can_activate` / `can_deactivate` / `ad_engage_pending`

> **注意**：改 Python 后必须重启 `run_web` 进程；只刷新前端不够。

## HMI 文言

| code | 文言 | 触发 |
|------|------|------|
| `ad_activate` | 功能已激活 | STANDBY→ACTIVE |
| `ad_exit` | 功能已退出 | ACTIVE→STANDBY |
| `speed_limit` | 限速切换：… | `v_limit` 变化（首帧只记基准） |
| `state_change` | 系统状态切换：A → B | 其余状态迁移 |

数据流：

```
state_change / 限速检测
  → event_bus "hmi_alert"
  → HMIManager
  → snapshot["hmi"] = { ad_state, alerts, latest, highest }
  → Web HmiPanel
```

关键文件：

- `hmi/hmi_manager.py` — 告警列表、`to_payload`、标准 code  
- `sim_server/session.py` — 发布文言、限速差分、写入 snapshot  
- `web/src/HmiPanel.tsx` — 前端窗口  

演示限速切换：默认 `acc_highway` 前段 12 m/s、后段 8 m/s（约 x=120 附近前瞻切换）。

## Web 演示步骤

```bash
cd /Users/ricka/PycharmProjects/PythonProject
source .venv/bin/activate
pytest
python run_web.py --rebuild
# 端口占用：lsof -ti:8000 | xargs kill -9
```

1. 打开 http://127.0.0.1:8000 ，点「开始」  
2. 等状态栏 **AD 待机**（约 t≥2.5s），点「激活」→ HMI「功能已激活」  
3. 点「退出」→ HMI「功能已退出」；或继续行驶观察「限速切换」  
4. 暂停后拖时间轴 / ←→ 回看  

## 测试

- `tests/test_hmi_session.py` — 激活 / 退出 / 限速文言  
- `tests/test_sim_session.py` — 手动激活、帧 seek、ACC 保持 ACTIVE  
- `tests/test_state_machine.py` — 状态机单元  

## 后续

见 `HANDOFF.md` §4：告警自动消失、OVERRIDE 演示、绕障等。
