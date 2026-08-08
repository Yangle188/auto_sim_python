# Changelog

本文件记录 AutoSim（`PythonProject`）面向用户的变更摘要。

## 2026-08-08

### P-UI1：仪表簇 + 通道条

- **InstrumentCluster** PIP（左下）：车速弧、限速/v*、AD 灯、ADAS 图标（LCC/ACC/FCW/AEB/Nudge/LC/Hands）、横向误差/d_gap/TTC、脱手进度条。
- **ChannelStrip** 底栏：speed / v_cmd / accel / steer / d_gap / TTC / lat_err / hands_off；可折叠；Author 默认折、Review 默认开。
- `data/selectors.ts` 统一派生指标（含客户端 lat_err）；仍用节流 `uiFrame`，不破坏 BirdEye 渲染隔离。

### P-UI0：仿真台壳 + 渲染隔离

- 工作模式 Author / Drive / Review；顶栏瘦身为 Transport；驾驶操作进 SideDock → Mission。
- `SafetyBanner` 承接 FCW/AEB/TOR/脱手告警；Scene / Events 分 Tab。
- **渲染隔离**：`BirdEyeViewport` 用 `frameRef` + `requestAnimationFrame`；WS 帧不触发视口 re-render。
- **绘制纯函数**：`paint(ctx, camera, frameData, layerFlags)` 内按 flags 开关图层。
- **事件穿透**：`ViewportHost` 随 SideDock 悬停切换 Canvas `pointer-events`。
- 架构约束见 `docs/FRONTEND_SIM_UI_ARCHITECTURE.md` §5.3 / §12。

### P6：感知驱动 AEB + 绕障/变道仲裁 + DMS 可配置

- **AEB 与 ACC 共用 leads 开关**：`use_truth_leads=False` 时 AEB/FCW 走 `_perception_leads()`（预测优先，融合框回退）；顶栏文案改为「Leads·真值/感知」。
- **绕障仲裁**：nudging 时同侧拨杆升格完整变道并 HMI「拨杆变道中断绕障」；反向拨杆拒绝（`nudge_conflict`）。
- **DMS 可配置**：场景字段 `hands_off_warn_s` / `hands_off_tor_s`；`set_teaching` 可热改；Web ConfigPanel 数字输入 + 顶栏脱手进度条。
- 测试：感知 AEB、nudge 仲裁、自定义脱手阈值；`pytest` 全量通过。

## 2026-08-06

### P5：绕障 nudge + DMS 脱手计时

- **Nudge**：`planning/nudge.py` 对本车道静止障碍做短距横向弓形路径（非完整变道）；预设 `nudge_demo`；场景字段 `nudge_enabled`。
- **DMS**：`safety/dms.py` ACTIVE 下累计脱手；约 6s 告警、12s 自动发 TOR；「双手在环」/快捷键 `H` 清零。
- HMI code：`nudge` / `hands_off`；顶栏显示绕障侧与脱手秒数。

### P4：感知闭环教学开关

- 场景字段 `use_truth_leads`（默认 True）/ `use_est_pose_lateral`（默认 False）。
- 关闭真值 leads 后 ACC 与变道间隙仅用感知融合+预测（P6 起 AEB 同步）。
- 开启估计横向后 Pure Pursuit 吃 EKF 位姿（易画龙）；默认真值位姿保持稳定。
- `POST /api/control` `action=set_teaching`；Web 顶栏与「教学闭环」配置可切换；HMI code=`teach`。

### P3：场景打磨（路口左转 + 脚本关键帧编辑）

- **路口拼接**：`urban_arterial` 增加左转连接道 `UR_TURN_EL_N` 与北向出口；中道多 successor（直行/左转）；鸟瞰绘制停车线。
- **选链 / auto-maneuver**：`follow_lane_chain(prefer_maneuver=)`；场景字段 `planned_maneuver`；距进口道末端 &lt;40m 自动切链并 HMI 日志。
- **预设**：`urban_left`（城市：路口左转）。
- **脚本障碍编辑**：ConfigPanel 支持匀速/脚本切换与关键帧 CRUD；画布绘制关键帧折线。
- **草稿角标**：draft≠applied 时面板与顶栏显示「草稿未应用」。

### P2：驾驶员责任（告警 toast + TOR / OVERRIDE）

- **HMI toast 优先级**：`snapshot.hmi.latest` 在时效窗口内按 INFO&lt;WARNING&lt;ALERT&lt;FAULT 选取，不再等于时间最新一条；事件日志 `alerts` 仍完整保留。
- **自动消失**：INFO 5s / WARNING 8s / ALERT 15s / FAULT 30s（`hmi/config.py`）；过期后顶栏可「暂无提示」，日志仍在。
- **TOR**：`POST /api/control` `action=tor`；Web「请求接管」；文言「请立即接管车辆」；`tor_pending` 状态位。
- **OVERRIDE**：`action=override` + 快捷键 `O`；ACTIVE→OVERRIDE 后 AD 纵向/横向指令归零；「退出」可从 OVERRIDE→STANDBY。
- 测试：`tests/test_override_tor.py`；HMI 优先级用例；`pytest` 约 137 passed。

## 2026-08-05

### L2 P1：车道级底图 + LCC + 拨杆变道 + FCW/AEB

- 新增 `map/lane_map.py`：Lane（中心线、虚实线、左右邻道、successor）与中心线 adapter。
- 教学底图：`highway_3lane`（可换道/实线禁换/限速分段）、`urban_arterial`（主干+路口停车线）；`GET /api/maps`、`/api/basemap?map_id=`。
- LCC：跟当前 `ego_lane` 中心线；snapshot 增加 `ego_lane_id` / `lane_index` / `lane_change` / `aeb`。
- 拨杆变道：`planning/lane_change.py`；`POST /api/control` `action=lane_change`；Web「左/右变道」与 `[` / `]`。
- FCW/AEB：`safety/aeb.py`，与 ACC 仲裁（AEB 优先盖写减速度）；HMI 文言。
- 默认预设改为 `highway_lcc`；新增 `highway_aeb`、`urban_arterial`；保留 `acc_highway` / `urban_turns`。
- **事件日志**：`SimSession._sim_log` 将场景启动、激活、变道、ACC、FCW/AEB、限速等写入 HMI「事件日志」面板。
- **鸟瞰左右**：heading-up 相机将车体左侧映射到屏幕左侧（原先左右镜像，导致「左/右变道」观感相反）。
- **变道视角**：相机航向锁定车道/道路中心线切向（`view.cam_yaw`），不再跟变道过渡曲线拧画面；自车仍可横向移动。
- **加速度 HUD**：snapshot 增加 `accel`（m/s²），鸟瞰左上角显示纵向加速度指令。
- **HMI 窗口**：可拖动标题栏移动；事件日志区可滚动，避免底部条目被裁切。

## 2026-08-02

### HMI / Web

- 鸟瞰左上角 **HMI 窗口**：展示功能激活状态与提示日志。
- 文言时机：**功能已激活** / **功能已退出** / **限速切换**；顶栏增加「退出」。
- `acc_highway` 后段限速改为 8 m/s，便于演示限速切换。

### 状态机 / Web

- **STANDBY→ACTIVE 需主动激活**：不再因车速自动切入；顶栏新增「激活」按钮（车速未就绪可挂起待切入）。

### Web / 仿真控制

- **时间轴**：可拖动跳转到历史帧（自动暂停回看）。
- **自车预瞄轨迹**：沿路径虚线 + Pure Pursuit 圆弧 + 预瞄点。
- **上一帧 / 下一帧**：暂停后可回看历史；在最新帧再点「下一帧」则单步推进仿真。快捷键 ← / →。
- 算路结果金黄高亮；可选「算路时保留障碍」。

### Planning（P0）

- 跟车/静态障碍间距改为**保险杠净空**（计入车头与障碍半长）。
- 本车道判定改为点到路径折线的**垂距**。

### Fixes（午后 review）

- 「开始/重置」会先写入当前草稿场景，避免改了配置仍跑旧 episode。
- ACC/静态制动导致车速 &lt;5m/s 时保持 ACTIVE，不再抖回 STANDBY。
- 静态障碍作为真值 lead 参与纵向减速；终点减速距离加大，按路线首段初始化位姿。
- 算路场景绘制底图全网车道线；JSON 导入保留 `base_map_id`。
- 脚本障碍拖拽平移全部关键帧；路点拖拽同步相邻路段衔接。
- 输入框内空格不再误触开始/暂停；`run_web` 修复便携 Node 找不到 `node`。

### Web UX

- 画布工具：浏览 / **算路** / **编路线** / **放障碍**。
- 编路线：全图鸟瞰点选追加或插入路点、拖拽移动；坐标文本改为可选高级项。
- 放障碍：点击放置、拖拽改位；动态障碍表单收敛为 vx/vy。
- 场景 JSON 导入 / 导出。

### Map / 导航

- 新增教学底图 `campus_grid`（3×3 节点双向路网）。
- Dijkstra 最短路 → `Route` 下发；API：`GET /api/basemap`、`POST /api/route/plan`。
- Web「算路」：点选起终点节点后写入草稿，应用并重开即可跟线。

### Docs / Handoff

- 交接文档更新为当前完成度与下一步（见 `HANDOFF.md`）。

### Localization / Viz（收工打磨）

- GPS 位置更新不再修正航向，减轻估计轨迹「假画龙」。
- Web：橙框为真值自车；定位估计改为青色标记点。

## 2026-08-01

### Planning / ACC

- 纵向时距跟车（ACC）：匹配前车速 + 间距误差修正；邻道不误跟。
- 预测轨切入本车道时提前减速（cut-in）；前车离开本车道后回升到限速（cut-out）。
- 默认场景 `acc_highway`：三车道直行走廊 + 脚本前车（跟车→切出→切入→再切出）。

### Control

- Pure Pursuit：路径弧长插值预瞄、\(L_d(v)\)、转角限速；横向闭环使用真值位姿。

### Visualize / Web

- 鸟瞰扩展为 **三车道**（外侧实线 + 车道虚线分隔）。
- 视角：**道路朝上**（相机航向跟路径切向，车道线不随自车 yaw 抖）；支持滚轮/按钮缩放。
- HUD 显示 ACC 间距/前车速。

### Simulator / World

- 车道宽 `LANE_WIDTH=3.2m`；`NUM_LANES=3`；自车宽 `VEHICLE_WIDTH=1.96m`、长 4.8m。
- 明确状态点 `(x,y)` = **后轴中心**，沿车道中心线；鸟瞰画车体矩形 + 后轴十字，并绘制多车道标线。

### Web Viz & Scene Config

- 新增 `SimSession` + `SceneConfig`：仿真步进与场景注入从 `main` 抽离，snapshot JSON 化。
- FastAPI：`/api/scene`、`/api/control`、WebSocket `/ws/sim` 实时推帧。
- React（Vite）鸟瞰 Canvas + 路线/障碍配置面板；**Apply & Restart** 重开 episode。
- CLI `python3 main.py` 仍走 matplotlib；入口 `python3 -m sim_server`。
- 一键脚本：`python3 run_web.py` / `./run_web.sh`（必要时自动 build、启动服务并打开浏览器；**自动使用项目 `.venv`**）。
- 自定义路线：路段支持中文名 / 主辅路 / 机动（左/右转等）；默认「城市：左右转+主辅路」预设；Web 界面与鸟瞰 HUD/图例中文化。

### Map

- 新增路线下发：`Link` / `Route` / `MapManager`；演示三段不同限速路线。
- `get_speed_limit` / `get_speed_limit_ahead` 供纵向规划；`TrajPlanner.plan(..., speed_limit=)` 以限速为基准速。
- `main` 用 demo route 替代手写三点路径；鸟瞰按 link 限速着色并显示 HUD `limit`。

### Visualize

- **仿真中可暂停**：交互窗口下按 `Space` 暂停/继续；暂停期间仿真主循环阻塞，窗口标题与 HUD 显示 `PAUSED`。
- **结束后保持界面**：仿真跑完后默认不立刻关闭鸟瞰窗；关闭窗口或按 `q` / `Esc` 再退出。可用 `visualize/config.py` 中 `HOLD_ON_FINISH = False` 关闭该行为。
- **重复播放**：窗口右下角 `Replay` 按钮（或按 `r`）可重跑整段仿真；运行中 / 暂停中 / 结束后均可触发；重播清空轨迹并重置场景。
- 新增接口：`block_while_paused()`、`hold_until_closed()`（返回 `replay`/`close`）、`prepare_replay()`、`consume_replay_request()`（`NullRenderer` / Agg 为空操作，不影响无头与 pytest）。

### Prediction

- 新增恒速（CV）障碍预测：检测聚类、最近邻跟踪、短时外推。
- `TrajPlanner.plan(..., predictions=)` 支持前瞻减速；场景增加横向穿越动态障碍。
- 鸟瞰绘制紫色虚线预测轨迹。

### Localization

- 新增 4 状态自行车模型 EKF（里程计预测 + 含噪 GPS）。
- 规划/控制/状态机使用估计位姿；感知仍用真值；鸟瞰叠加估计轨迹。

### Planning

- 路径密化（`PathPlanner`）+ 纵向调速（`TrajPlanner`：障碍/终点/预测）。

### Control

- Pure Pursuit 横向跟踪 + 纵向 P 控制；公开 `get_lookahead_point` 供可视化。

### Docs / Tooling

- 交接文档 `HANDOFF.md`、日总结 `docs/SUMMARY_2026-08-01_daily.md`、`SUMMARY_*_web_viz/simulator/map.md`、`README.md`、`scaffold_config.json` 同步。
- 运行依赖：`matplotlib`（CLI 可视化）、`fastapi`/`uvicorn`（Web）；核心仿真 / EKF / 预测仍无强制数值库。
- 一键入口：`run_web.py` / `run_web.sh`。
