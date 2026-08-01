import type { Maneuver, ObstacleIn, PresetMeta, RoadClass, RouteLink, SceneConfig } from "./types";
import { MANEUVER_ZH, ROAD_CLASS_ZH } from "./labels";

interface Props {
  draft: SceneConfig;
  onChange: (next: SceneConfig) => void;
  onApply: () => void;
  presets: PresetMeta[];
  onLoadPreset: (id: string) => void;
  busy: boolean;
  error: string | null;
}

function pointsToText(points: [number, number][]): string {
  return points.map(([x, y]) => `${x},${y}`).join(" | ");
}

function parsePoints(text: string): [number, number][] | null {
  const parts = text
    .split("|")
    .map((s) => s.trim())
    .filter(Boolean);
  if (parts.length < 2) return null;
  const pts: [number, number][] = [];
  for (const p of parts) {
    const [xs, ys] = p.split(",").map((t) => t.trim());
    const x = Number(xs);
    const y = Number(ys);
    if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
    pts.push([x, y]);
  }
  return pts;
}

export function ConfigPanel({
  draft,
  onChange,
  onApply,
  presets,
  onLoadPreset,
  busy,
  error,
}: Props) {
  const updateLink = (idx: number, patch: Partial<RouteLink>) => {
    const links = draft.links.map((l, i) => (i === idx ? { ...l, ...patch } : l));
    onChange({ ...draft, links });
  };

  const updateObstacle = (idx: number, patch: Partial<ObstacleIn>) => {
    const obstacles = draft.obstacles.map((o, i) => {
      if (i !== idx) return o;
      const next = { ...o, ...patch };
      if (next.dynamic && !next.motion) {
        next.motion = {
          type: "linear",
          vx: 0,
          vy: 1.5,
          x0: next.x,
          y0: next.y,
        };
      }
      if (!next.dynamic) next.motion = null;
      return next;
    });
    onChange({ ...draft, obstacles });
  };

  const addLink = () => {
    const last = draft.links[draft.links.length - 1];
    const end = last?.points[last.points.length - 1] || [0, 0];
    onChange({
      ...draft,
      links: [
        ...draft.links,
        {
          link_id: `L${draft.links.length + 1}`,
          name: "自定义路段",
          points: [end, [end[0] + 20, end[1]]],
          speed_limit: 8,
          road_class: "main",
          maneuver: "straight",
        },
      ],
    });
  };

  const removeLink = (idx: number) => {
    if (draft.links.length <= 1) return;
    onChange({ ...draft, links: draft.links.filter((_, i) => i !== idx) });
  };

  const addObstacle = () => {
    onChange({
      ...draft,
      obstacles: [
        ...draft.obstacles,
        { x: 30, y: 3, width: 2, height: 2, dynamic: false, motion: null },
      ],
    });
  };

  const removeObstacle = (idx: number) => {
    onChange({
      ...draft,
      obstacles: draft.obstacles.filter((_, i) => i !== idx),
    });
  };

  return (
    <aside className="panel">
      <header className="panel-head">
        <h2>场景配置</h2>
        <button type="button" className="btn primary" onClick={onApply} disabled={busy}>
          应用并重开
        </button>
      </header>
      {error && <p className="error">{error}</p>}

      <section className="block">
        <div className="block-head">
          <h3>预设路线</h3>
        </div>
        <p className="hint">可先加载示例，再改点列/限速/主辅路；改完点「应用并重开」。</p>
        <div className="preset-list">
          {presets.map((p) => (
            <button
              key={p.id}
              type="button"
              className="btn preset"
              disabled={busy}
              title={p.description}
              onClick={() => onLoadPreset(p.id)}
            >
              <strong>{p.title}</strong>
              <span>{p.description}</span>
            </button>
          ))}
        </div>
      </section>

      <label className="field">
        <span>路线 ID</span>
        <input
          value={draft.route_id}
          onChange={(e) => onChange({ ...draft, route_id: e.target.value })}
        />
      </label>
      <label className="field">
        <span>仿真时长（秒）</span>
        <input
          type="number"
          min={1}
          step={1}
          value={draft.duration_s}
          onChange={(e) =>
            onChange({ ...draft, duration_s: Number(e.target.value) || 20 })
          }
        />
      </label>

      <section className="block">
        <div className="block-head">
          <h3>路段（可自定义左右转 / 主辅路）</h3>
          <button type="button" className="btn small" onClick={addLink}>
            + 路段
          </button>
        </div>
        {draft.links.map((link, idx) => (
          <div className="link-block" key={`${link.link_id}-${idx}`}>
            <div className="card-row link-meta">
              <input
                className="id"
                value={link.link_id}
                onChange={(e) => updateLink(idx, { link_id: e.target.value })}
                title="路段 ID"
              />
              <input
                className="name"
                value={link.name || ""}
                onChange={(e) => updateLink(idx, { name: e.target.value })}
                title="中文名称"
                placeholder="中文名称"
              />
              <select
                value={link.road_class || "main"}
                onChange={(e) =>
                  updateLink(idx, { road_class: e.target.value as RoadClass })
                }
                title="主路/辅路"
              >
                {Object.entries(ROAD_CLASS_ZH).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
              <select
                value={link.maneuver || "straight"}
                onChange={(e) =>
                  updateLink(idx, { maneuver: e.target.value as Maneuver })
                }
                title="机动类型"
              >
                {Object.entries(MANEUVER_ZH).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
              <input
                className="num"
                type="number"
                step={0.5}
                value={link.speed_limit}
                onChange={(e) =>
                  updateLink(idx, { speed_limit: Number(e.target.value) || 1 })
                }
                title="限速 m/s"
              />
              <button type="button" className="btn small danger" onClick={() => removeLink(idx)}>
                ×
              </button>
            </div>
            <input
              className="pts full"
              value={pointsToText(link.points)}
              onChange={(e) => {
                const pts = parsePoints(e.target.value);
                if (pts) updateLink(idx, { points: pts });
              }}
              title="折线点：x,y | x,y | …（转弯请加中间点）"
              placeholder="折线点 x,y | x,y | …"
            />
          </div>
        ))}
        <p className="hint">
          相邻路段首尾需衔接。左右转请在折线中加拐点，例如右转：
          <code>50,0 | 58,-4 | 62,-18</code>
        </p>
      </section>

      <section className="block">
        <div className="block-head">
          <h3>障碍物</h3>
          <button type="button" className="btn small" onClick={addObstacle}>
            + 障碍
          </button>
        </div>
        {draft.obstacles.map((o, idx) => (
          <div className="obs-block" key={idx}>
            <div className="card-row">
              <input
                className="num"
                type="number"
                step={0.5}
                value={o.x}
                onChange={(e) => updateObstacle(idx, { x: Number(e.target.value) })}
                title="x"
              />
              <input
                className="num"
                type="number"
                step={0.5}
                value={o.y}
                onChange={(e) => updateObstacle(idx, { y: Number(e.target.value) })}
                title="y"
              />
              <input
                className="num"
                type="number"
                step={0.1}
                value={o.width}
                onChange={(e) => updateObstacle(idx, { width: Number(e.target.value) })}
                title="宽"
              />
              <input
                className="num"
                type="number"
                step={0.1}
                value={o.height}
                onChange={(e) => updateObstacle(idx, { height: Number(e.target.value) })}
                title="高"
              />
              <label className="check">
                <input
                  type="checkbox"
                  checked={o.dynamic}
                  onChange={(e) => updateObstacle(idx, { dynamic: e.target.checked })}
                />
                动态
              </label>
              <button
                type="button"
                className="btn small danger"
                onClick={() => removeObstacle(idx)}
              >
                ×
              </button>
            </div>
            {o.dynamic && o.motion && o.motion.type === "linear" && (
              <div className="card-row sub">
                <span className="muted">vx</span>
                <input
                  className="num"
                  type="number"
                  step={0.1}
                  value={o.motion.vx}
                  onChange={(e) => {
                    const m = o.motion;
                    if (!m || m.type !== "linear") return;
                    updateObstacle(idx, {
                      motion: { ...m, vx: Number(e.target.value) },
                    });
                  }}
                />
                <span className="muted">vy</span>
                <input
                  className="num"
                  type="number"
                  step={0.1}
                  value={o.motion.vy}
                  onChange={(e) => {
                    const m = o.motion;
                    if (!m || m.type !== "linear") return;
                    updateObstacle(idx, {
                      motion: { ...m, vy: Number(e.target.value) },
                    });
                  }}
                />
                <span className="muted">x0</span>
                <input
                  className="num"
                  type="number"
                  step={0.5}
                  value={o.motion.x0}
                  onChange={(e) => {
                    const m = o.motion;
                    if (!m || m.type !== "linear") return;
                    updateObstacle(idx, {
                      motion: { ...m, x0: Number(e.target.value) },
                    });
                  }}
                />
                <span className="muted">y0</span>
                <input
                  className="num"
                  type="number"
                  step={0.5}
                  value={o.motion.y0}
                  onChange={(e) => {
                    const m = o.motion;
                    if (!m || m.type !== "linear") return;
                    updateObstacle(idx, {
                      motion: { ...m, y0: Number(e.target.value) },
                    });
                  }}
                />
              </div>
            )}
            {o.dynamic && o.motion && o.motion.type === "scripted" && (
              <div className="card-row sub">
                <span className="muted">
                  脚本运动 · {o.motion.keyframes.length} 关键帧（跟车/切入/切出剧本）
                </span>
              </div>
            )}
          </div>
        ))}
      </section>
    </aside>
  );
}
