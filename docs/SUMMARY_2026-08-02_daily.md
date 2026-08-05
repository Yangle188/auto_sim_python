# 2026-08-02 收工总览

> 上午接续 ACC / 反画龙；下午完成 Web UX、底图算路、手动激活与 HMI。细则见 `SUMMARY_2026-08-02_web_hmi.md`。

## 今日结论

主链路已可教学演示：**底图算路 / 画布编辑 → 手动激活 AD → ACC 跟线 → HMI 文言 → 时间轴回看**。  
默认场景 `acc_highway`（后段限速 8 m/s，便于看限速提示）。

## 已落地（可演示）

1. Web 工具：浏览 / 算路 / 编路线 / 放障碍；场景 JSON 导入导出  
2. 教学底图 `campus_grid` + 起终点 Dijkstra 算路  
3. ACC：保险杠净空、垂距本车道、静态障碍真值 lead  
4. 时间轴 + 上一帧/下一帧 + 自车预瞄轨迹  
5. **STANDBY→ACTIVE 手动「激活」**；「退出」回 STANDBY  
6. **HMI 窗口**：功能状态 + 激活/退出/限速切换文言  
7. `pytest` 以仓库当前结果为准（编写本文时约 124 passed）

## 文档索引（今日相关）

| 文档 | 内容 |
|------|------|
| [auto_sim_learning.md](auto_sim_learning.md) | **完整学习手册**（各模块四段式） |
| [SUMMARY_2026-08-02_web_hmi.md](SUMMARY_2026-08-02_web_hmi.md) | Web / 状态机 / HMI 专题 |
| [../HANDOFF.md](../HANDOFF.md) | 交接与下一步 |
| [../CHANGELOG.md](../CHANGELOG.md) | 面向用户的变更列表 |
| [../README.md](../README.md) | 快速开始与模块总览 |

## 关键文件

| 路径 | 备注 |
|------|------|
| `framework/state_machine.py` | 五态 AD |
| `hmi/hmi_manager.py` | 告警与 snapshot 载荷 |
| `sim_server/session.py` | 激活/退出、HMI 发布、帧历史 |
| `web/src/HmiPanel.tsx` / `App.tsx` / `Timeline.tsx` | HMI / 控制 / 时间轴 |
| `web/src/BirdEyeCanvas.tsx` | 鸟瞰 + 预瞄 |
| `map/demo_base_map.py` / `router.py` | 底图与算路 |
| `planning/traj_planner.py` | ACC |

## 启动

```bash
cd /Users/ricka/PycharmProjects/PythonProject
source .venv/bin/activate
pytest
python run_web.py --rebuild
```

## 下一步（摘要）

见 `HANDOFF.md`：HMI 告警自动消失、OVERRIDE、路口车道线、绕障等。
