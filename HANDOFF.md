# AutoSim 交接文档（HANDOFF）

> 目的：让后续会话（人或 Agent）不依赖聊天上下文，即可从当前状态继续开发。  
> 最后更新：2026-08-08 晚（收工；明天优先 **P-UI2**）  
> 项目路径：`/Users/ricka/PycharmProjects/PythonProject`  
> 远程：`git@github.com:Yangle188/auto_sim_python.git`（`main`）  
> **注意：本机大量改动尚未 commit/push，续做前先 `git status`。**

---

## 1. 一句话现状

后端教学 L2+（P1–P6）已齐：LaneMap / LCC / 变道 / ACC / AEB / TOR / 路口左转 / 关键帧 / leads 真值·感知 / nudge 仲裁 / 可配置 DMS。  
前端仿真台 **P-UI0 壳 + P-UI1 仪表/通道** 已落地；下一步拆 BEV 图层（P-UI2）。  
默认场景 `highway_lcc`；绕障 `nudge_demo`。

---

## 2. 本轮已完成（相对上一交接）

### 2.1 后端 P6

| 项 | 说明 |
|----|------|
| 感知 AEB | `use_truth_leads` 驱动 ACC / AEB / 变道间隙；关则 `_perception_leads()` |
| 绕障仲裁 | 同侧拨杆升格变道 +「中断绕障」；反向 `nudge_conflict` |
| DMS | `hands_off_warn_s` / `hands_off_tor_s`；可热改；Cluster 内脱手条 |

### 2.2 前端 P-UI0 / P-UI1

| 项 | 关键路径 |
|----|----------|
| 模式 Author/Drive/Review | `web/src/app/modeMachine.ts` · `App.tsx` |
| SideDock Mission/Scene/Events | `web/src/layout/SideDock.tsx` · `docks/MissionDock.tsx` |
| SafetyBanner | `web/src/hmi/SafetyBanner.tsx` |
| 渲染隔离 BEV | `BirdEyeCanvas.tsx` → `paint` + `frameRef` + rAF；导出 `BirdEyeViewport` |
| 事件穿透 | `ViewportHost` ↔ SideDock hover → Canvas `pointer-events` |
| 仪表簇 PIP | `web/src/cluster/InstrumentCluster.tsx` |
| 通道条 | `web/src/layout/ChannelStrip.tsx` |
| 指标派生 | `web/src/data/selectors.ts`（含客户端 `lat_err`） |
| 架构文档 | `docs/FRONTEND_SIM_UI_ARCHITECTURE.md`（含 §5.3 / §12 三条强制约束） |

**三条强制约束（续做前端必须遵守）：**

1. **渲染隔离**：帧只写 `frameRef.current`，禁止因仿真帧触发 `BirdEyeViewport` re-render。  
2. **绘制纯函数**：`paint(ctx, camera, frameData, layerFlags)`，内部按 flags 开关；禁止预处理 `frameData`。  
3. **事件穿透**：SideDock 悬停时切断 BEV `pointer-events`。

---

## 3. 环境与验证

```bash
cd /Users/ricka/PycharmProjects/PythonProject
source .venv/bin/activate
pytest                          # 预期 ~151 passed
python3 run_web.py --rebuild    # 前端改动后务必 rebuild（静态 dist）
```

本机若无系统 `npm`，可用 Cursor 自带 node 构建：

```bash
cd web
NODE=/Applications/Cursor.app/Contents/Resources/app/resources/helpers/node
"$NODE" ./node_modules/typescript/bin/tsc --noEmit
"$NODE" ./node_modules/vite/bin/vite.js build
```

**手测烟测：**

1. Drive：开始 → 激活 → 左下仪表有速度/AD；底栏通道有数值。  
2. 鼠标移入右侧 Dock：滚轮不应缩放 BEV。  
3. `nudge_demo` 绕障仲裁；AEB 场景切「Leads·感知」仍能 FCW/AEB。  
4. ACTIVE 脱手 → 告警/TOR；`H` 清零。

---

## 4. 明天优先：P-UI2（图层系统）

架构见 [docs/FRONTEND_SIM_UI_ARCHITECTURE.md](docs/FRONTEND_SIM_UI_ARCHITECTURE.md) §5.2 / §11 P-UI2。

### 目标

1. 将 `BirdEyeCanvas.tsx` 内巨型 `paint` **按域拆到** `web/src/viewports/layers/*`（仍由统一 `paint` 编排，签名不变）。  
2. SideDock 增加 **Layers** Tab（或 Dock）：分组开关 + 教学对比预设（只看真值障碍 / 只看融合 / 规划+控制）。  
3. `layerFlags` 进 `uiStore`（可用 `useState` + `localStorage`，按 mode 分存）；经 **ref** 喂给 rAF，**不要**每帧 setState。  
4. 验收：可单独关闭预测/融合，做感知课对比演示。

### 建议 Layer ID（已有默认值）

见 `web/src/viewports/types.ts` → `DEFAULT_LAYER_FLAGS`  
（`map.network` / `perc.fused` / `pred.traj` / `ctrl.pp_preview` / `ego.*` 等）

### 非目标（明天不要做）

- 全量 3D / 多相机  
- Protobuf 总线  
- 擅自 commit/push（除非用户明确要求）

### 其后可选

- **P-UI3**：InspectorDock + Events 过滤 + 通道 sparkline  
- nudge 也绑 `use_truth_leads`（当前为 demo 稳定仍用真值）

---

## 5. 文档索引

| 文档 | 用途 |
|------|------|
| [docs/FRONTEND_SIM_UI_ARCHITECTURE.md](docs/FRONTEND_SIM_UI_ARCHITECTURE.md) | **前端仿真台架构（权威）** |
| [docs/auto_sim_learning.md](docs/auto_sim_learning.md) | 模块学习手册 |
| [CHANGELOG.md](CHANGELOG.md) | 变更摘要（含 P6 / P-UI0 / P-UI1） |
| [README.md](README.md) | 快速开始 |
| [seprompt.md](seprompt.md) | 完整 L2+ 蓝图（非实现范围） |

---

## 6. 给后续 Agent

> 启动：`source .venv/bin/activate` → `pytest` → `python3 run_web.py --rebuild`。  
> 前端入口：`web/src/App.tsx`；BEV：`BirdEyeViewport`（实现仍在 `BirdEyeCanvas.tsx`）。  
> 帧路径：WS `frame` → `frameRef` → rAF `paint`；UI 铬（仪表/Banner）用 ~200ms 节流 `uiFrame`。  
> 后端 leads：`session._use_truth_leads`；nudge 仍 `_truth_leads()`。  
> **明天直接做 P-UI2**；改完跑 `tsc` + `pytest` + rebuild；**勿擅自 commit/push**。
