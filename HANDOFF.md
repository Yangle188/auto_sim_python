# AutoSim 交接文档（HANDOFF）

> 目的：让后续会话（人或 Agent）不依赖聊天上下文，即可从当前状态继续开发。  
> 最后更新：2026-08-01  
> 项目路径：`/Users/ricka/PycharmProjects/PythonProject`

---

## 1. 一句话现状

模块化自动驾驶仿真原型（AutoSim）主链路已齐：状态机、仿真、感知、HMI、控制、规划、可视化、定位、**预测（CV）**；`pytest` 全绿。后续以打磨与扩展为主。

---

## 2. 环境与验证

```bash
cd /Users/ricka/PycharmProjects/PythonProject
source .venv/bin/activate
pip install -r requirements.txt   # pytest + matplotlib
pytest
python main.py                    # 20s；鸟瞰可关
```

- 核心仿真 / EKF / 预测无第三方数值库；visualize 需 matplotlib。
- `visualize/config.py`：`ENABLE_VISUALIZE = False` 可关窗；`HOLD_ON_FINISH` 控制结束后是否保持窗口。
- 鸟瞰：`Space` 暂停；`Replay`/`r` 重播；结束后关窗或 `q` 退出。变更见 `CHANGELOG.md`。

---

## 3. 模块完成度

| 模块 | 状态 | 关键文件 |
|------|------|----------|
| `config/` … `visualize/` | ✅ | 见既有 SUMMARY |
| `localization/` | ✅ | EKF + GPS |
| **`prediction/`** | ✅ **今日完成** | `predictor.py`；`tests/test_prediction.py` |

脚手架：`scaffold_config.json`（`skip_exist_file: true`）。

---

## 4. 主循环数据流

```
动态障碍真值更新
true → 感知融合 → predictor.step → predictions
est (EKF) → PathPlanner / TrajPlanner(predictions) / PurePursuit
→ world.step → EKF.predict + GPS → Renderer(true, est, predictions)
```

---

## 5. Prediction 接口

```python
from prediction.predictor import ObstaclePredictor

predictions = ObstaclePredictor().step(fused_obstacles, dt=DT)
v_cmd = TrajPlanner().plan(est, path, fused, predictions)
```

场景：静态旁侧障碍 + 动态障碍 \(x=60,\;y=-8+1.5t\)。

---

## 6. 建议的下一任务

1. 打磨 planning：几何绕障、曲率调速  
2. 打磨 control：\(L_d(v)\)、段上插值预瞄  
3. 打磨 localization：IMU 观测、与车辆积分对齐  
4. 打磨 visualize：录帧 / GIF  
5. 打磨 prediction：多模态 / 简单交互  

---

## 7. 回归检查清单

- [ ] `pytest`
- [ ] `python main.py` 完整跑完；ACTIVE 后沿路径前进，末端附近靠拢 `(100,2)`
- [ ] 感知用真值、控制用估计
- [ ] `ENABLE_VISUALIZE=False` 时 main 仍可跑通

---

## 8. 相关文档

| 文档 | 内容 |
|------|------|
| `docs/SUMMARY_2026-08-01_prediction.md` | CV 预测 |
| `docs/SUMMARY_2026-08-01_localization.md` | EKF |
| `docs/SUMMARY_2026-08-01_visualize.md` | 鸟瞰 |
| `docs/SUMMARY_2026-08-01_planning.md` | planning |
| `docs/SUMMARY_2026-07-31_control.md` | Pure Pursuit |
| `README.md` | 入门 |

---

## 9. 给后续 Agent 的最短指令

> 阅读 `HANDOFF.md`。主模块已齐，优先按第 6 节打磨。保持真值→感知、估计→控制、`predictions`→TrajPlanner。改完跑 `pytest` 与 `python main.py`。
