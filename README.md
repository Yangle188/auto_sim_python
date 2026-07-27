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
├── tests/                  # 单元测试
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

> 根目录遗留的 `config.py` 已移除；Python 统一从 `config/` 包导入全局配置。

## 已实现模块

- **framework** — 五态状态机（OFF → PASSIVE → STANDBY → ACTIVE → OVERRIDE）+ 发布/订阅事件总线
- **simulator** — 运动学自行车模型、静态障碍物、参考路径
- **perception** — 激光雷达与摄像头模拟（距离/FOV 过滤、噪声、类别识别）及空间匹配融合
- **hmi** — 订阅 `hmi_alert` 主题，分级告警管理

## 规划中模块

`scaffold_config.json` 中已规划但尚未实现：localization、prediction、planning、control、visualize。

运行脚手架可创建空目录占位：

```bash
python project_scaffold.py
```

## 环境要求

- Python 3.10+（已在 3.14 下验证）
- 运行时无第三方依赖

## 快速开始

```bash
# 创建并激活虚拟环境
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 安装开发依赖（pytest）
pip install -r requirements.txt

# 运行仿真
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
4. ACTIVE 阶段以 10 m/s 为目标速度巡航
5. 每帧更新感知链路并发布 `perception_update` 事件

## 状态机激活条件

激活自动驾驶需同时满足：

- 当前状态为 **STANDBY**
- 车速在 **5.0 ~ 30.0 m/s** 范围内（见 `framework/config.py`）

## 许可证

暂无开源许可证，仅供学习与研究使用。
