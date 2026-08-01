# AutoSim — 自动驾驶仿真框架

Python 实现的模块化自动驾驶仿真原型，涵盖状态机、物理仿真、多传感器感知融合与人机交互告警，采用事件总线解耦各模块。

## 项目结构

```
PythonProject/
├── main.py                 # 仿真主入口
├── config/                 # 全局共享配置（步长、状态枚举、HMI 等级）
├── framework/              # 核心框架（状态机、事件总线）
├── simulator/              # 物理仿真（自行车模型、障碍物、参考路径）
├── perception/             # 感知（激光雷达 / 摄像头模拟 + 融合）
├── hmi/                    # 人机交互告警管理
├── control/                # Pure Pursuit 横向跟踪 + 纵向速度 P 控制
├── planning/               # 路径密化 + 纵向目标车速规划
├── visualize/              # matplotlib 鸟瞰渲染（车辆/路径/预瞄/障碍）
├── localization/           # 自行车模型 EKF 定位（GPS + 里程计）
├── prediction/             # 恒速障碍预测（跟踪 + 短时外推）
├── map/                    # 路线下发（Link/Route）与限速查询
├── tests/                  # 单元测试
├── docs/                   # 开发总结等文档
├── HANDOFF.md              # 交接文档（继续开发请先读）
├── project_scaffold.py     # 项目脚手架生成脚本
└── scaffold_config.json    # 完整 AD 栈目录规划
```

## 配置说明

配置按模块拆分，避免重复定义：

| 文件 | 内容 |
|------|------|
| `config/base_config.py` | 仿真步长 `DT`、AD 状态枚举、HMI 告警等级 |
| `framework/config.py` | 状态机切换阈值（激活车速范围、自检超时等） |
| `simulator/config.py` | 车辆动力学参数（轴距、最大车速、加减速度、转角） |
| `perception/config.py` | 激光雷达 / 摄像头检测范围、FOV、噪声、检测概率 |
| `hmi/config.py` | 告警列表容量等 HMI 参数 |
| `control/config.py` | 预瞄距离、巡航速、纵向 Kp、STANDBY 加速度 |
| `planning/config.py` | 路径密化分辨率、巡航速、障碍/终点减速参数 |
| `visualize/config.py` | 可视化开关、刷新间隔、图尺寸、轨迹长度 |
| `localization/config.py` | GPS 周期/噪声、过程噪声、初始协方差 |
| `prediction/config.py` | 预测时域、关联距离、coast、速度阈值 |
| `map/config.py` | 前方限速前瞻距离、link 衔接容差 |

> 根目录遗留的 `config.py` 已移除；Python 统一从 `config/` 包导入全局配置。

## 已实现模块

- **framework** — 五态状态机（OFF → PASSIVE → STANDBY → ACTIVE → OVERRIDE）+ 发布/订阅事件总线
- **simulator** — 运动学自行车模型、静态障碍物、参考路径
- **perception** — 激光雷达与摄像头模拟（距离/FOV 过滤、噪声、类别识别）及空间匹配融合
- **hmi** — 订阅 `hmi_alert` 主题，分级告警管理
- **control** — Pure Pursuit 路径跟踪 + 纵向速度 P 控制（已接入 `main.py`）
- **planning** — 参考路径密化 + 基于障碍/终点的纵向 `target_speed`（已接入 `main.py`）
- **visualize** — matplotlib 鸟瞰：车辆、航点/密化路径、预瞄点、障碍与融合检测、HUD（含估计轨迹）
- **localization** — 4 状态 EKF（里程计预测 + 含噪 GPS）；规划/控制吃估计位姿，感知吃真值
- **prediction** — 融合检测最近邻跟踪 + 恒速短时预测，供 TrajPlanner 前瞻减速
- **map** — Route/Link 路线下发与限速查询；`main` 下发演示路线，纵向规划吃 `speed_limit`

## 规划中模块

主栈模块已按 `scaffold_config.json` 落地；后续以打磨（绕障、\(L_d(v)\)、录帧等）为主。

## 文档

- [HANDOFF.md](HANDOFF.md) — 交接与继续开发指引
- [docs/SUMMARY_2026-08-01_map.md](docs/SUMMARY_2026-08-01_map.md) — map 模块开发总结
- [docs/SUMMARY_2026-08-01_prediction.md](docs/SUMMARY_2026-08-01_prediction.md) — prediction 模块开发总结
- [docs/SUMMARY_2026-08-01_localization.md](docs/SUMMARY_2026-08-01_localization.md) — localization / EKF 开发总结
- [docs/SUMMARY_2026-08-01_visualize.md](docs/SUMMARY_2026-08-01_visualize.md) — visualize 模块开发总结
- [docs/SUMMARY_2026-08-01_planning.md](docs/SUMMARY_2026-08-01_planning.md) — planning 模块开发总结与算法原理
- [docs/SUMMARY_2026-07-31_control.md](docs/SUMMARY_2026-07-31_control.md) — control 模块开发总结与算法原理

运行脚手架可创建空目录占位：

```bash
python project_scaffold.py
```

## 环境要求

- Python 3.10+（已在 3.14 下验证）
- 核心仿真、EKF、预测无第三方数值库依赖；鸟瞰可视化需要 `matplotlib`（见 `requirements.txt`）
- 关闭窗口渲染：将 `visualize/config.py` 中 `ENABLE_VISUALIZE` 设为 `False`
- 鸟瞰交互：`Space` 暂停/继续；`Replay` 按钮或 `r` 重播；结束后窗口默认保持，关窗或 `q` 退出（`HOLD_ON_FINISH`）
- 变更记录见 [CHANGELOG.md](CHANGELOG.md)

## 快速开始

```bash
# 创建并激活虚拟环境
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 安装依赖（pytest + matplotlib）
pip install -r requirements.txt

# 运行仿真（默认弹出鸟瞰图）
python main.py

# 运行全部测试
pytest
```

也可不安装 pytest，直接运行单个测试文件：

```bash
PYTHONPATH=. python tests/test_state_machine.py
```

## 仿真流程

`main.py` 默认运行 20 秒闭环仿真：

1. t=0.5s 上电（OFF → PASSIVE）
2. t=2.5s 自检通过（PASSIVE → STANDBY）
3. STANDBY 阶段加速，车速 ≥ 5 m/s 时激活 AD（STANDBY → ACTIVE）
4. 启动时下发 demo Route（多段不同限速）；PathPlanner 密化 waypoints
5. 每帧感知融合 → ObstaclePredictor；`MapManager.get_speed_limit_ahead` + 预测/障碍 → TrajPlanner
6. ACTIVE 阶段用 EKF 估计位姿做 Pure Pursuit（基准速为地图限速，近终点/障碍再减速）
7. 每帧 EKF 预测并按 GPS 周期融合含噪位置；鸟瞰显示真值、估计、预测与按限速着色的 route links

## 状态机激活条件

激活自动驾驶需同时满足：

- 当前状态为 **STANDBY**
- 车速在 **5.0 ~ 30.0 m/s** 范围内（见 `framework/config.py`）

## 许可证

暂无开源许可证，仅供学习与研究使用。
