# AutoSim 交接文档（HANDOFF）

> 目的：让后续会话（人或 Agent）不依赖聊天上下文，即可从当前状态继续开发。  
> 最后更新：2026-08-01  
> 项目路径：`/Users/ricka/PycharmProjects/PythonProject`

---

## 1. 一句话现状

模块化自动驾驶仿真原型（AutoSim）主链路已齐，并支持 **Web 实时鸟瞰 + 场景配置面板**（Route/障碍 Apply & Restart）；CLI matplotlib 仍可用。`pytest` 全绿。

---

## 2. 环境与验证

```bash
cd /Users/ricka/PycharmProjects/PythonProject
source .venv/bin/activate
pip install -r requirements.txt   # pytest + matplotlib + fastapi
pytest
python main.py                    # CLI 20s；鸟瞰可关

# Web UI（推荐一键）
python run_web.py                 # 自动 build（若需要）+ 开服务 + 打开浏览器
# 开发热更新仍可用: python -m sim_server 与 cd web && npm run dev
```

- 核心仿真无第三方数值库；visualize 需 matplotlib；Web 需 fastapi/uvicorn + Node 构建前端。
- 变更见 `CHANGELOG.md`。

---

## 3. 模块完成度

| 模块 | 状态 | 关键文件 |
|------|------|----------|
| `config/` … `map/` | ✅ | 见既有 SUMMARY |
| **`sim_server/` + `web/`** | ✅ **今日完成** | `session.py` / `app.py`；`web/src/*`；`tests/test_sim_session.py` |

---

## 4. 主循环数据流

```
SceneConfig → SimSession.reset/start/step_once → JSON snapshot
  → matplotlib Renderer（CLI）或 WebSocket → React Canvas
MapManager + TrajPlanner(speed_limit) + predictions 同前
```

---

## 5. Web 接口摘要

- `GET/PUT /api/scene` — 草稿/已应用场景
- `POST /api/control` — start/pause/resume/reset
- `WS /ws/sim` — frame + status
- 配置面板改 draft，**应用并重开** 才重建 episode（非运行中热改）
- 默认预设 `urban_turns`：主路→右转辅路→辅路→左转汇入主路；路段字段 `name` / `road_class` / `maneuver`
- Web UI 中文；鸟瞰标注路段名、主辅路、机动与限速

详见 `docs/SUMMARY_2026-08-01_web_viz.md`。

---

## 6. 建议的下一任务

1. 打磨 planning：几何绕障、曲率调速  
2. 打磨 control：\(L_d(v)\)、段上插值预瞄  
3. Web：画布点选添加障碍、运行中热改（需额外同步策略）  
4. 打磨 localization / prediction  

---

## 7. 回归检查清单

- [ ] `pytest`
- [ ] `python main.py`（`ENABLE_VISUALIZE=False`）可跑完
- [ ] `python -m sim_server` + 浏览器 Start 可见车辆沿路线运动
- [ ] Apply & Restart 改限速/障碍后新 episode 生效

---

## 8. 相关文档

| 文档 | 内容 |
|------|------|
| `docs/SUMMARY_2026-08-01_web_viz.md` | Web 推流与场景配置 |
| `docs/SUMMARY_2026-08-01_map.md` | Route / Link 限速 |
| `README.md` | 入门 |

---

## 9. 给后续 Agent 的最短指令

> 阅读 `HANDOFF.md`。仿真步进在 `SimSession`；网页入口 `python -m sim_server` + `web/`。改完跑 `pytest`；Web 改动需 `cd web && npm run build`。
