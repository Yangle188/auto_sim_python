# AutoSim 交接文档（HANDOFF）

> 目的：让后续会话（人或 Agent）不依赖聊天上下文，即可从当前状态继续开发。  
> 最后更新：2026-08-02（HMI 窗口）  
> 项目路径：`/Users/ricka/PycharmProjects/PythonProject`  
> 远程：`git@github.com:Yangle188/auto_sim_python.git`（`main`）

---

## 1. 一句话现状

主链路可演示：算路/编辑 → SimSession → Web 鸟瞰。**手动激活 AD**；左上角 **HMI 窗口**显示功能状态，并在激活/退出/限速切换时出文言。默认 `acc_highway`（后段限速 8 m/s）。

---

## 2. 本轮完成

| 项 | 说明 |
|----|------|
| HMI 窗口 | `web/src/HmiPanel.tsx`：功能状态 + 最新提示 + 日志 |
| 文言 | 功能已激活 / 功能已退出 / 限速切换（写入 snapshot.hmi） |
| 退出 | 顶栏「退出」→ `deactivate`（ACTIVE→STANDBY） |

---

## 3. 环境与验证

```bash
cd /Users/ricka/PycharmProjects/PythonProject
source .venv/bin/activate
pytest
python run_web.py --rebuild
# 端口占用：lsof -ti:8000 | xargs kill -9
```

操作：开始 → 待机后「激活」→ HMI 显示「功能已激活」→「退出」或过限速变化点看提示。

---

## 4. 下一步建议

### HMI / 状态机
1. 告警自动消失（`ALERT_AUTO_CLEAR_S`）  
2. OVERRIDE 演示入口  

### P1
3. 转弯自动标 maneuver；路口车道线拼接  
4. 第二张教学底图  

### P2
5. 脚本障碍关键帧编辑器；draft≠applied 角标  

### P3
6. 简单绕障/换道  

---

## 5. 给后续 Agent

> 先读 §4。仿真：`python run_web.py --rebuild`（改 Python 后必须重启进程）。几何只动 `simulator/config.py`。  
> 改完 `pytest`；勿擅自 commit/push（除非用户要求）。
