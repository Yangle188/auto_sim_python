# Web 实时渲染与场景配置（2026-08-01）

## 目标

- 浏览器鸟瞰实时渲染（主交互入口）
- 配置路线 Link/限速、障碍物后 **应用并重开** episode
- CLI `python main.py` + matplotlib 仍可用

## 架构

- `sim_server/session.py`：`SimSession` 步进仿真，snapshot JSON 化
- `sim_server/scene_schema.py`：`SceneConfig`（Pydantic）+ 预设
- `sim_server/app.py`：FastAPI REST + WebSocket
- `web/`：Vite + React + Canvas（中文 UI）
- `run_web.py`：一键 build（若需）+ 启服务 + 开浏览器；**自动切到项目 `.venv`**

## API

| 接口 | 说明 |
|------|------|
| `GET /api/scene` | draft / applied / status |
| `PUT /api/scene` | 写入草稿（校验 Route） |
| `GET /api/presets` | 预设列表与完整 scene |
| `POST /api/control` | `start` / `pause` / `resume` / `reset` |
| `WS /ws/sim` | `{type:"frame"|"status", data:...}` |

Snapshot 另含：`lane_left` / `lane_right` / `vehicle_geom`（见 simulator 几何 SUMMARY）。

## 启动

```bash
cd PythonProject
# 首次：source .venv/bin/activate && pip install -r requirements.txt

# 推荐（无需先 activate；脚本会切到 .venv）
python run_web.py              # 或 ./run_web.sh
python run_web.py --rebuild    # 前端有改动时

# 开发双端
.venv/bin/python -m sim_server # :8000
cd web && npm run dev          # :5173 代理 API/WS
```

**排障**：`ModuleNotFoundError: uvicorn` → 旧版脚本用了系统 Python；当前 `run_web.py` 已按 `sys.prefix` 检测并切换 `.venv`。端口占用：`lsof -ti:8000 | xargs kill -9`。

## 配置生效策略

编辑面板只改 draft；**应用并重开** = `PUT /api/scene` + `reset` + `start`。不在运行中热改拓扑。

## 自定义路线 / 主辅路

路段字段：`name`（中文）、`road_class`（`main`/`aux`）、`maneuver`（`straight`/`left`/`right`/`merge`/`diverge`）。

预设：

- `urban_turns`：主路直行 → 右转进辅路 → 辅路直行 → 左转汇入 → 主路直行
- `simple`：旧近直线三段

鸟瞰：主路实线、辅路虚线；路段中点中文标注；车道边界；后轴十字；HUD/图例中文。

## 测试

```bash
pytest tests/test_sim_session.py
pytest
```
