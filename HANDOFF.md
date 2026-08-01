# AutoSim 交接文档（HANDOFF）

> 目的：让后续会话（人或 Agent）不依赖聊天上下文，即可从当前状态继续开发。  
> 最后更新：2026-08-01（收工）  
> 项目路径：`/Users/ricka/PycharmProjects/PythonProject`

---

## 1. 一句话现状

AutoSim 主链路已齐：**Map 路线限速 → SimSession → Web 实时鸟瞰/场景配置**；世界几何：**车道 3.2m、车宽 1.96m、后轴中心贴车道中心线**。Web 一键启动已本地跑通。`pytest`：**94 passed**。今日收工，明天从第 6 节继续。

---

## 2. 今日完成（2026-08-01）

| 项 | 说明 |
|----|------|
| Map | `Link`/`Route`/`MapManager`；限速查询 + 前瞻；`TrajPlanner.speed_limit` |
| SimSession | `main` 抽离为可注入 `SceneConfig` 的步进会话；snapshot JSON 化 |
| Web | FastAPI + WS 推帧；React Canvas；中文 UI；预设「左右转+主辅路」 |
| 一键启动 | `python run_web.py` / `./run_web.sh`（**自动切到项目 `.venv`**） |
| World 几何 | `LANE_WIDTH=3.2`、`VEHICLE_WIDTH=1.96`；车道边界；后轴系车体外形 |

日总结：`docs/SUMMARY_2026-08-01_daily.md`。

---

## 3. 环境与验证

```bash
cd /Users/ricka/PycharmProjects/PythonProject
# 首次或依赖缺失时：
# source .venv/bin/activate && pip install -r requirements.txt

pytest
python run_web.py                 # 推荐；无需先 activate（会自动用 .venv）
python run_web.py --rebuild       # 前端有改动时
# CLI：visualize/config.py → ENABLE_VISUALIZE=False 可关窗
python main.py
```

**注意**

- `run_web.py` 若检测到项目 `.venv` 且当前不在其中，会 `exec` 切换后再启动，避免系统 Python 找不到 `uvicorn`。
- 本机若无全局 `npm`，会尝试 `~/.local/node/bin/npm`；已有 `web/dist` 可直接起服务。
- 端口占用：`lsof -ti:8000 | xargs kill -9`。
- 核心仿真无强制数值库；CLI 需 matplotlib；Web 需 fastapi/uvicorn + Node（构建 `web/`）。
- 变更总览：`CHANGELOG.md`。

---

## 4. 模块完成度

| 模块 | 状态 | 关键入口 |
|------|------|----------|
| framework / simulator / perception / hmi | ✅ | 既有 SUMMARY |
| control / planning / localization / prediction | ✅ | 既有 SUMMARY |
| map | ✅ | `map/map_manager.py`；`docs/SUMMARY_2026-08-01_map.md` |
| sim_server + web | ✅ | `run_web.py`；`docs/SUMMARY_2026-08-01_web_viz.md` |
| simulator 几何 | ✅ 今日末 | `simulator/config.py` + `geometry.py`；`docs/SUMMARY_2026-08-01_simulator.md` |

脚手架：`scaffold_config.json`（`skip_exist_file: true`）。

---

## 5. 主循环数据流

```
SceneConfig（路线/障碍）
  → SimSession.step_once
      → MapManager(waypoints, speed_limit_ahead)
      → 感知(真值) → Predictor → TrajPlanner(speed_limit, predictions)
      → PurePursuit(est) → world.step → EKF
      → snapshot(+ lane_left/right, vehicle_geom)
  → WS/React 或 matplotlib Renderer
```

**约定**

- 参考路径 / dense path = **车道中心线**
- 车辆状态 `(x,y)` = **后轴中心**（应在中心线上）
- 感知吃真值；规划/控制/状态机吃 EKF 估计
- 场景配置：面板改 draft → **应用并重开**（非运行中热改拓扑）

---

## 6. 明天建议优先（按序）

1. **World / 场景一致性**：障碍横向位置相对 3.2m 车道再校准；可选画出车宽与车道间隙  
2. **Control**：预瞄 \(L_d(v)\)、段上插值；确认后轴模型下 Pure Pursuit 横向误差  
3. **Planning**：曲率限速；几何绕障（车宽 1.96 在 3.2 车道内约 0.62m/侧余量）  
4. **Web UX**：画布点选加障碍/路点；可选录帧  
5. **Localization / Prediction**：按需小步打磨  

未做（刻意）：运行中热改路线、多客户端、WebGL 3D。

---

## 7. 回归检查清单

- [x] `pytest`（94 passed，车宽 1.96）
- [x] `python run_web.py` / `./run_web.sh` 可启动（自动 `.venv`）  
- [ ] 「开始」可见沿 `urban_turns` 行驶、车道灰线、后轴十字、车宽观感正常  
- [ ] 预设切换 +「应用并重开」生效  
- [ ] `ENABLE_VISUALIZE=False` 时 `python main.py` 可跑完  

---

## 8. 相关文档

| 文档 | 内容 |
|------|------|
| `docs/SUMMARY_2026-08-01_daily.md` | **今日收工总览（明天先读）** |
| `docs/SUMMARY_2026-08-01_web_viz.md` | Web / SceneConfig |
| `docs/SUMMARY_2026-08-01_simulator.md` | 车道与后轴几何 |
| `docs/SUMMARY_2026-08-01_map.md` | Route / Link 限速 |
| `docs/SUMMARY_2026-08-01_*.md` | planning / viz / loc / prediction |
| `docs/SUMMARY_2026-07-31_control.md` | Pure Pursuit |
| `CHANGELOG.md` | 面向用户的变更摘要 |
| `README.md` | 入门与启动 |

---

## 9. 给后续 Agent 的最短指令

> 先读 `HANDOFF.md` 与 `docs/SUMMARY_2026-08-01_daily.md`。  
> 仿真步进在 `SimSession`；Web 用 `python run_web.py`（会自动进 `.venv`；前端改完加 `--rebuild`）。  
> 几何常量只改 `simulator/config.py`（车道 3.2 / 车宽 1.96 / 后轴参考点）。  
> 改完跑 `pytest`；勿改无关模块、勿擅自 commit。
