# 2026-08-02 收工总览

> 接续 08-01 夜：ACC / 三车道 / 反画龙。明日主攻 Web UX 与 Map 底图导航。

## 今日结论

- **真值车**在直线 ACC 场景横向几乎贴中线（控制吃真值 + PP 弧长预瞄）。  
- 用户感到「画龙更严重」主因是：**车道线固定后，带噪 EKF 估计车体更显眼**；已改为 GPS 不修 yaw、降噪，估计只画青点。  
- 远程已有：`45f17b7`（ACC/三车道/PP）。收工时本地可能还有 localization + BirdEye 未提交改动，开工先看 `git status`。

## 已落地能力（可演示）

1. 默认 `acc_highway`：跟车 → 切出加速 → 切入减速 → 再切出  
2. 三车道标线 + 道路朝上鸟瞰 + 滚轮/按钮缩放  
3. ACC HUD（间距 / 前车速 / source）  
4. `pytest` 107 passed  

## 明日计划（用户指定）

### 1）仿真界面整理

- 路线加载更便捷（少手填坐标；画布交互 / 更好预设流）  
- 障碍物加载更便捷（点选放置、拖拽、简化动态障碍配置）  
- 面板信息架构收敛  

### 2）Map：底图 + 起终点算路

- 生成一张 **base 底图**（教学路网）  
- 底图上选 **起点 / 终点** → 自动算路  
- 下发导航 `Route` → 自车沿导航路线行驶  

建议实现顺序见 `HANDOFF.md` §6。

## 关键文件

| 路径 | 备注 |
|------|------|
| `planning/traj_planner.py` | ACC |
| `control/pure_pursuit.py` | 横向跟踪 |
| `localization/ekf_localizer.py` | GPS 不改 yaw |
| `web/src/BirdEyeCanvas.tsx` / `ConfigPanel.tsx` | 明日 UX 主战场 |
| `map/*` | 明日底图/算路扩展点 |
| `sim_server/scene_schema.py` | 场景与脚本障碍 |

## 启动

```bash
cd /Users/ricka/PycharmProjects/PythonProject
pytest
python run_web.py --rebuild
```
