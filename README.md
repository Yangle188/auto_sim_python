# AutoSim — 自动驾驶仿真框架

Python 实现的模块化自动驾驶仿真原型，涵盖状态机、物理仿真、多传感器感知融合与人机交互告警，采用事件总线解耦各模块。Web 端提供实时鸟瞰、场景编辑与 HMI 提示。

## 项目结构

```
PythonProject/
├── main.py                 # CLI 仿真主入口
├── run_web.py              # Web 一键启动（构建前端 + uvicorn）
├── config/                 # 全局共享配置（步长、状态枚举、HMI 等级）
├── framework/              # 核心框架（状态机、事件总线）
├── simulator/              # 物理仿真（自行车模型、障碍物、参考路径）
├── perception/             # 感知（激光雷达 / 摄像头模拟 + 融合）
├── hmi/                    # 人机交互告警管理
├── control/                # Pure Pursuit 横向跟踪 + 纵向速度 P 控制
├── planning/               # 路径密化 + 纵向目标车速规划（ACC）
├── visualize/              # matplotlib 鸟瞰渲染
├── localization/           # 自行车模型 EKF 定位（GPS + 里程计）
├── prediction/             # 恒速障碍预测
├── map/                    # Route/Link、车道级 LaneMap、教学底图、算路
├── safety/                 # FCW / AEB 纵向安全
├── sim_server/             # FastAPI + SimSession（Web 推流 / 场景 API）
├── web/                    # Vite + React 鸟瞰、配置、HMI、时间轴
├── tests/                  # 单元测试
├── docs/                   # 开发总结
├── HANDOFF.md              # 交接文档（继续开发请先读）
├── CHANGELOG.md            # 面向用户的变更记录
└── project_scaffold.py     # 项目脚手架
```

## 配置说明

配置按模块拆分，避免重复定义：

| 文件 | 内容 |
|------|------|
| `config/base_config.py` | 仿真步长 `DT`、AD 状态枚举、HMI 告警等级 |
| `framework/config.py` | 状态机切换阈值（激活车速范围、自检超时等） |
| `simulator/config.py` | 动力学 + 车道 3.2m、三车道、车宽 1.96m、后轴几何 |
| `perception/config.py` | 激光雷达 / 摄像头检测范围、FOV、噪声、检测概率 |
| `hmi/config.py` | 告警列表容量等 HMI 参数 |
| `control/config.py` | 预瞄距离、巡航速、纵向 Kp、STANDBY 加速度 |
| `planning/config.py` | 路径密化、巡航速、ACC 时距/最小间距、障碍减速 |
| `visualize/config.py` | 可视化开关、heading-up 视野、刷新间隔 |
| `localization/config.py` | GPS 周期/噪声、过程噪声、初始协方差 |
| `prediction/config.py` | 预测时域、关联距离、coast、速度阈值 |
| `map/config.py` | 前方限速前瞻距离、link 衔接容差 |

## 已实现模块

- **framework** — 五态状态机（OFF → PASSIVE → STANDBY → ACTIVE → OVERRIDE）+ 事件总线  
- **simulator** — 运动学自行车模型（后轴中心）、三车道、静态/脚本动态障碍  
- **perception** — 激光雷达与摄像头模拟及空间匹配融合  
- **hmi** — 订阅 `hmi_alert`；事件日志 + 优先级 toast（自动消失）；TOR / 接管文言  
- **control** — Pure Pursuit + 纵向 P 控制；预瞄轨迹可供 Web 绘制  
- **planning** — 路径密化 + 时距 ACC（保险杠净空、垂距本车道）+ 终点减速  
- **visualize** — matplotlib 鸟瞰（车头向上、三车道）  
- **localization** — 4 状态 EKF；规划吃估计，横向控制吃真值（教学稳定）  
- **prediction** — 融合检测跟踪 + 恒速短时预测  
- **map** — Route/Link 限速；**LaneMap** 车道级拓扑；`highway_3lane` / `urban_arterial` / `campus_grid`  
- **safety** — FCW / AEB（TTC + 净空，盖写纵向）  
- **sim_server / web** — 实时鸟瞰、画布编辑、算路、时间轴、激活/退出、拨杆变道、TOR/接管、HMI  

## 规划中 / 下一步

详见 [`HANDOFF.md`](HANDOFF.md)：P1–P6 已收口后的可选增强。

### 已具备的教学 L2+ 能力（至 2026-08-08 / P6 + P-UI1）

- **车道级底图** / **LCC** / **拨杆变道** / **路口 auto-maneuver**
- **FCW·AEB** / **ACC** / **TOR·OVERRIDE**
- **脚本关键帧** / **草稿角标** / **Leads 真值·感知开关（ACC+AEB+变道间隙）**
- **同车道绕障 nudge（与拨杆仲裁）** / **可配置 DMS 脱手计时**
- **仿真台 UI**：Author/Drive/Review · Mission Dock · SafetyBanner · **仪表簇** · **通道条**

## 文档

- [docs/auto_sim_learning.md](docs/auto_sim_learning.md) — **模块学习手册**（架构图 / 原理 / 核心逻辑 / 数据接口，面向初学者）
- [HANDOFF.md](HANDOFF.md) — 交接与继续开发指引
- [CHANGELOG.md](CHANGELOG.md) — 变更摘要
- [docs/SUMMARY_2026-08-05_daily.md](docs/SUMMARY_2026-08-05_daily.md) — 2026-08-05 收工总览（L2 P1 + UX）
- [docs/SUMMARY_2026-08-05_l2_p1.md](docs/SUMMARY_2026-08-05_l2_p1.md) — LaneMap / LCC / 变道 / AEB
- [docs/SUMMARY_2026-08-02_daily.md](docs/SUMMARY_2026-08-02_daily.md) — 2026-08-02 收工总览
- [docs/SUMMARY_2026-08-02_web_hmi.md](docs/SUMMARY_2026-08-02_web_hmi.md) — Web / 手动激活 / HMI
- [docs/SUMMARY_2026-08-01_acc_viz.md](docs/SUMMARY_2026-08-01_acc_viz.md) — ACC / 三车道 / 鸟瞰
- [docs/SUMMARY_2026-08-01_daily.md](docs/SUMMARY_2026-08-01_daily.md) — 2026-08-01 日收工总览
- [docs/SUMMARY_2026-08-01_web_viz.md](docs/SUMMARY_2026-08-01_web_viz.md) — Web 实时渲染与场景配置
- [docs/SUMMARY_2026-08-01_simulator.md](docs/SUMMARY_2026-08-01_simulator.md) — 车道/后轴几何
- [docs/SUMMARY_2026-08-01_map.md](docs/SUMMARY_2026-08-01_map.md) — map 模块
- [docs/SUMMARY_2026-08-01_prediction.md](docs/SUMMARY_2026-08-01_prediction.md) — prediction 模块
- [docs/SUMMARY_2026-08-01_localization.md](docs/SUMMARY_2026-08-01_localization.md) — localization / EKF
- [docs/SUMMARY_2026-08-01_visualize.md](docs/SUMMARY_2026-08-01_visualize.md) — visualize 模块
- [docs/SUMMARY_2026-08-01_planning.md](docs/SUMMARY_2026-08-01_planning.md) — planning 模块
- [docs/SUMMARY_2026-07-31_control.md](docs/SUMMARY_2026-07-31_control.md) — control 模块

## 环境要求

- Python 3.10+（已在 3.14 下验证）
- 核心仿真无强制数值库；CLI 鸟瞰需要 `matplotlib`；Web 需要 `fastapi` / `uvicorn` 与 Node.js（构建 `web/`）
- 关闭 CLI 窗口渲染：`visualize/config.py` 中 `ENABLE_VISUALIZE = False`
- Web：`python3 run_web.py`；前端有改动加 `--rebuild`；**改 Python 后必须重启进程**

## 快速开始

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# CLI 仿真（matplotlib）
python3 main.py

# Web 仿真（推荐）
python3 run_web.py
# 前端有改动: python3 run_web.py --rebuild
# 端口占用: lsof -ti:8000 | xargs kill -9

pytest
```

## Web 演示流程（推荐）

1. `python3 run_web.py --rebuild`，浏览器打开提示的地址  
2. 预设选「高速：LCC + 拨杆变道」或「高速：FCW / AEB」（也可算路/编路线）  
3. 点「开始」→ 约 t≥2.5s 进入 **待机(STANDBY)**  
4. 车速接近可激活区间后点「**激活**」→ HMI 提示「功能已激活」  
5. LCC：观察跟车道；「左/右变道」或 `[` / `]` 拨杆变道；AEB 预设看 FCW→紧急制动  
6. 「暂停」后可拖 **时间轴** 或 ←/→ 逐帧回看  

## CLI 仿真流程（`main.py`）

默认约 20 秒闭环（CLI 仍可能按旧逻辑演示；**Web 路径以手动激活为准**）：

1. t=0.5s 上电（OFF → PASSIVE）  
2. t=2.5s 自检通过（PASSIVE → STANDBY）  
3. STANDBY 加速；Web 上需点「激活」进入 ACTIVE  
4. 感知融合 → 预测 → 限速/ACC → Pure Pursuit  
5. EKF 定位；鸟瞰显示真值、估计、预测与 route  

## 状态机激活条件

进入 **ACTIVE** 需同时满足：

- 当前状态为 **STANDBY**
- 收到驾驶员激活请求（Web「激活」或 `action=activate`）
- 车速在 **5.0 ~ 30.0 m/s**（见 `framework/config.py`）；未达速时可先请求，达速后自动切入  

退出：**退出**按钮或 `action=deactivate`，或车速超出工作范围等事件 → STANDBY。

## 许可证

暂无开源许可证，仅供学习与研究使用。
