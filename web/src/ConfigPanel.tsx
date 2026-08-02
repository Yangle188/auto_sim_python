import { useRef, useState } from "react";
import type { Maneuver, ObstacleIn, PresetMeta, RoadClass, RouteLink, SceneConfig } from "./types";
import { MANEUVER_ZH, ROAD_CLASS_ZH } from "./labels";
import type { EditTool } from "./sceneEdit";

interface Props {
  draft: SceneConfig;
  onChange: (next: SceneConfig) => void;
  onApply: () => void;
  presets: PresetMeta[];
  onLoadPreset: (id: string) => void;
  busy: boolean;
  error: string | null;
  editTool: EditTool;
  onEditTool: (tool: EditTool) => void;
  selectedLinkIdx: number;
  onSelectLink: (idx: number) => void;
  selectedObstacleIdx: number | null;
  onSelectObstacle: (idx: number | null) => void;
  keepObstaclesOnNav: boolean;
  onKeepObstaclesOnNav: (v: boolean) => void;
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
  editTool,
  onEditTool,
  selectedLinkIdx,
  onSelectLink,
  selectedObstacleIdx,
  onSelectObstacle,
  keepObstaclesOnNav,
  onKeepObstaclesOnNav,
}: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [showCoords, setShowCoords] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);

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
    const links = [
      ...draft.links,
      {
        link_id: `L${draft.links.length + 1}`,
        name: "自定义路段",
        points: [end, [end[0] + 20, end[1]]] as [number, number][],
        speed_limit: 8,
        road_class: "main" as RoadClass,
        maneuver: "straight" as Maneuver,
      },
    ];
    onChange({ ...draft, links });
    onSelectLink(links.length - 1);
    onEditTool("route");
  };

  const removeLink = (idx: number) => {
    if (draft.links.length <= 1) return;
    onChange({ ...draft, links: draft.links.filter((_, i) => i !== idx) });
    onSelectLink(Math.max(0, idx - 1));
  };

  const addObstacle = () => {
    const obstacles = [
      ...draft.obstacles,
      { x: 30, y: 3, width: 2, height: 2, dynamic: false, motion: null },
    ];
    onChange({ ...draft, obstacles });
    onSelectObstacle(obstacles.length - 1);
    onEditTool("obstacle");
  };

  const removeObstacle = (idx: number) => {
    onChange({
      ...draft,
      obstacles: draft.obstacles.filter((_, i) => i !== idx),
    });
    onSelectObstacle(null);
  };

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(draft, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${draft.route_id || "scene"}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const importJson = async (file: File) => {
    setImportError(null);
    try {
      const text = await file.text();
      const data = JSON.parse(text) as SceneConfig;
      if (!data.links?.length) throw new Error("缺少 links");
      onChange({
        route_id: data.route_id || "imported",
        links: data.links,
        obstacles: data.obstacles || [],
        duration_s: data.duration_s || 20,
        base_map_id: data.base_map_id ?? null,
      });
    } catch (e) {
      setImportError(String((e as Error).message || e));
    }
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
      {importError && <p className="error">{importError}</p>}

      <section className="block">
        <div className="block-head">
          <h3>画布工具</h3>
        </div>
        <div className="tool-row tool-row-4">
          {(
            [
              ["none", "浏览"],
              ["nav", "算路"],
              ["route", "编路线"],
              ["obstacle", "放障碍"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={`btn tool${editTool === id ? " active" : ""}`}
              disabled={busy}
              onClick={() => onEditTool(id)}
            >
              {label}
            </button>
          ))}
        </div>
        <p className="hint">
          {editTool === "none"
            ? "浏览运行画面。改场景：算路 / 编路线 / 放障碍。"
            : editTool === "nav"
              ? "底图上依次点选起点、终点节点，自动最短路并高亮写入草稿。"
              : editTool === "route"
                ? "画布点选追加/插入路点，拖拽移动；面板改路段属性。"
                : "画布点击空白放置障碍，拖拽改位置；Delete 删除选中。"}
        </p>
        {editTool === "nav" && (
          <label className="check keep-obs">
            <input
              type="checkbox"
              checked={keepObstaclesOnNav}
              onChange={(e) => onKeepObstaclesOnNav(e.target.checked)}
            />
            算路时保留当前障碍
          </label>
        )}
      </section>

      <section className="block">
        <div className="block-head">
          <h3>预设一键加载</h3>
        </div>
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
        <div className="panel-actions">
          <button type="button" className="btn small" onClick={exportJson} disabled={busy}>
            导出 JSON
          </button>
          <button
            type="button"
            className="btn small"
            disabled={busy}
            onClick={() => fileRef.current?.click()}
          >
            导入 JSON
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void importJson(f);
              e.target.value = "";
            }}
          />
        </div>
      </section>

      <div className="meta-row">
        <label className="field compact">
          <span>路线 ID</span>
          <input
            value={draft.route_id}
            onChange={(e) => onChange({ ...draft, route_id: e.target.value })}
          />
        </label>
        <label className="field compact">
          <span>时长 (s)</span>
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
      </div>

      <section className="block">
        <div className="block-head">
          <h3>路段</h3>
          <button type="button" className="btn small" onClick={addLink}>
            + 路段
          </button>
        </div>
        {draft.links.map((link, idx) => {
          const selected = idx === selectedLinkIdx;
          return (
            <div
              className={`link-block${selected ? " selected" : ""}`}
              key={`${link.link_id}-${idx}`}
              onClick={() => {
                onSelectLink(idx);
                if (editTool === "none") onEditTool("route");
              }}
            >
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
                <button
                  type="button"
                  className="btn small danger"
                  onClick={(e) => {
                    e.stopPropagation();
                    removeLink(idx);
                  }}
                >
                  ×
                </button>
              </div>
              <p className="hint pts-summary">
                {link.points.length} 个路点
                {selected ? " · 画布编辑中" : " · 点击选中"}
              </p>
              {showCoords && selected && (
                <input
                  className="pts full"
                  value={pointsToText(link.points)}
                  onChange={(e) => {
                    const pts = parsePoints(e.target.value);
                    if (pts) updateLink(idx, { points: pts });
                  }}
                  onClick={(e) => e.stopPropagation()}
                  title="折线点：x,y | x,y | …"
                  placeholder="折线点 x,y | x,y | …"
                />
              )}
            </div>
          );
        })}
        <button
          type="button"
          className="btn small ghost"
          onClick={() => setShowCoords((v) => !v)}
        >
          {showCoords ? "隐藏坐标文本" : "显示坐标文本（高级）"}
        </button>
      </section>

      <section className="block">
        <div className="block-head">
          <h3>障碍物</h3>
          <button type="button" className="btn small" onClick={addObstacle}>
            + 障碍
          </button>
        </div>
        {draft.obstacles.length === 0 && (
          <p className="hint">暂无障碍。切到「放障碍」后在画布点击放置。</p>
        )}
        {draft.obstacles.map((o, idx) => {
          const selected = idx === selectedObstacleIdx;
          return (
            <div
              className={`obs-block${selected ? " selected" : ""}`}
              key={idx}
              onClick={() => {
                onSelectObstacle(idx);
                if (editTool === "none") onEditTool("obstacle");
              }}
            >
              <div className="card-row obs-compact">
                <span className="obs-pos">
                  ({o.x.toFixed(1)}, {o.y.toFixed(1)})
                </span>
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
                <label className="check" onClick={(e) => e.stopPropagation()}>
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
                  onClick={(e) => {
                    e.stopPropagation();
                    removeObstacle(idx);
                  }}
                >
                  ×
                </button>
              </div>
              {o.dynamic && o.motion && o.motion.type === "linear" && (
                <div className="card-row sub" onClick={(e) => e.stopPropagation()}>
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
                </div>
              )}
              {o.dynamic && o.motion && o.motion.type === "scripted" && (
                <p className="hint">脚本运动 · {o.motion.keyframes.length} 关键帧（预设剧本）</p>
              )}
            </div>
          );
        })}
      </section>
    </aside>
  );
}
