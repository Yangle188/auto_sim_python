# 2026-08-06 收工总览

> 本日：P2 → P3 → P4 → **P5**。细则见 `CHANGELOG.md`。

## 今日结论

教学路线图 **P1–P5 收口**：含绕障 nudge、脱手计时→TOR。  
`pytest`：以仓库当前结果为准（编写时约 **145+** passed）。

## 已落地（摘要）

| 阶段 | 内容 |
|------|------|
| P2 | Toast 优先级；TOR / OVERRIDE |
| P3 | 路口左转；关键帧编辑；草稿角标 |
| P4 | ACC 真值/感知；横向真值/估计 |
| P5 | 同车道 nudge；DMS 脱手计时 |

## 演示（P5）

```text
高速：同车道绕障 nudge → 激活 → 看路径弓形绕障
任意场景激活 → 等脱手告警/TOR →「双手在环」(H) 清零
```

## 启动

```bash
source .venv/bin/activate
pytest
python3 run_web.py --rebuild
```

## 下一步

见 `HANDOFF.md` §4：可选增强（感知 AEB、仲裁细化等）。
