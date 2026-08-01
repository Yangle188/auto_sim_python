# Web 实时渲染与场景配置（2026-08-01）

## 目标

- 浏览器鸟瞰实时渲染（替代简陋 matplotlib 交互为主入口）
- 配置路线 Link/限速、障碍物后 **Apply & Restart** 重开 episode
- CLI `python main.py` + matplotlib 仍可用

## 架构

- `sim_server/session.py`：`SimSession` 步进仿真，snapshot JSON 化
- `sim_server/scene_schema.py`：`SceneConfig`（Pydantic）
- `sim_server/app.py`：FastAPI REST + WebSocket
- `web/`：Vite + React + Canvas

## API

| 接口 | 说明 |
|------|------|
| `GET /api/scene` | draft / applied / status |
| `PUT /api/scene` | 写入草稿（校验 Route） |
| `POST /api/control` | `start` / `pause` / `resume` / `reset` |
| `WS /ws/sim` | `{type:"frame"|"status", data:...}` |

## 启动

```bash
# 后端
cd PythonProject
source .venv/bin/activate
pip install -r requirements.txt
python -m sim_server          # http://127.0.0.1:8000

# 前端开发（另开终端）
cd web
npm install
npm run dev                   # http://127.0.0.1:5173 代理到 8000

# 生产：先 build 再只开后端（挂载 web/dist）
npm run build
python -m sim_server
```

## 配置生效策略

编辑面板只改 draft；**应用并重开** = `PUT /api/scene` + `reset` + `start`。不在运行中热改拓扑。

## 自定义路线 / 主辅路

路段字段：`name`（中文）、`road_class`（`main`/`aux`）、`maneuver`（`straight`/`left`/`right`/`merge`/`diverge`）。

预设：`GET /api/presets`

- `urban_turns`：主路直行 → 右转进辅路 → 辅路直行 → 左转汇入 → 主路直行
- `simple`：旧近直线三段

鸟瞰：主路实线、辅路虚线；路段中点中文标注；HUD/图例中文。

## 测试

```bash
pytest tests/test_sim_session.py
pytest
```
