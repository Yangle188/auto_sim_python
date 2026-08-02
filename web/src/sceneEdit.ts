import type { BaseMapData, ObstacleIn, Point, SceneConfig } from "./types";

export type EditTool = "none" | "route" | "obstacle" | "nav";

export interface WorldBounds {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
}

function finalizeBounds(
  minX: number,
  maxX: number,
  minY: number,
  maxY: number,
  pad: number
): WorldBounds {
  if (!Number.isFinite(minX)) {
    return { minX: -20, maxX: 60, minY: -25, maxY: 25 };
  }
  const spanX = Math.max(20, maxX - minX);
  const spanY = Math.max(20, maxY - minY);
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  return {
    minX: cx - spanX / 2 - pad,
    maxX: cx + spanX / 2 + pad,
    minY: cy - spanY / 2 - pad,
    maxY: cy + spanY / 2 + pad,
  };
}

export function draftBounds(draft: SceneConfig, pad = 12): WorldBounds {
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;

  const grow = (x: number, y: number) => {
    minX = Math.min(minX, x);
    maxX = Math.max(maxX, x);
    minY = Math.min(minY, y);
    maxY = Math.max(maxY, y);
  };

  for (const link of draft.links) {
    for (const [x, y] of link.points) grow(x, y);
  }
  for (const o of draft.obstacles) {
    grow(o.x - o.width / 2, o.y - o.height / 2);
    grow(o.x + o.width / 2, o.y + o.height / 2);
  }

  return finalizeBounds(minX, maxX, minY, maxY, pad);
}

export function baseMapBounds(base: BaseMapData, pad = 12): WorldBounds {
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (const n of base.nodes) {
    minX = Math.min(minX, n.x);
    maxX = Math.max(maxX, n.x);
    minY = Math.min(minY, n.y);
    maxY = Math.max(maxY, n.y);
  }
  return finalizeBounds(minX, maxX, minY, maxY, pad);
}

export function nearestBaseNode(
  base: BaseMapData,
  wx: number,
  wy: number,
  maxDist: number
): string | null {
  let best: { id: string; d: number } | null = null;
  for (const n of base.nodes) {
    const d = Math.hypot(n.x - wx, n.y - wy);
    if (d <= maxDist && (!best || d < best.d)) best = { id: n.node_id, d };
  }
  return best?.id ?? null;
}

export function distPoint(a: Point, b: Point): number {
  return Math.hypot(a[0] - b[0], a[1] - b[1]);
}

/** 点到折线段最近点与段索引 */
export function nearestOnPolyline(
  pts: Point[],
  wx: number,
  wy: number
): { dist: number; seg: number; t: number; px: number; py: number } {
  let best = { dist: Infinity, seg: 0, t: 0, px: pts[0]?.[0] ?? 0, py: pts[0]?.[1] ?? 0 };
  for (let i = 0; i < pts.length - 1; i++) {
    const [x0, y0] = pts[i];
    const [x1, y1] = pts[i + 1];
    const dx = x1 - x0;
    const dy = y1 - y0;
    const L2 = dx * dx + dy * dy;
    const t = L2 < 1e-12 ? 0 : Math.max(0, Math.min(1, ((wx - x0) * dx + (wy - y0) * dy) / L2));
    const px = x0 + t * dx;
    const py = y0 + t * dy;
    const d = Math.hypot(wx - px, wy - py);
    if (d < best.dist) best = { dist: d, seg: i, t, px, py };
  }
  return best;
}

export function hitWaypoint(
  draft: SceneConfig,
  wx: number,
  wy: number,
  radius: number
): { linkIdx: number; pointIdx: number } | null {
  let best: { linkIdx: number; pointIdx: number; d: number } | null = null;
  for (let li = 0; li < draft.links.length; li++) {
    const pts = draft.links[li].points;
    for (let pi = 0; pi < pts.length; pi++) {
      const d = distPoint(pts[pi], [wx, wy]);
      if (d <= radius && (!best || d < best.d)) best = { linkIdx: li, pointIdx: pi, d };
    }
  }
  return best ? { linkIdx: best.linkIdx, pointIdx: best.pointIdx } : null;
}

export function hitObstacle(
  draft: SceneConfig,
  wx: number,
  wy: number
): number | null {
  let best: { idx: number; d: number } | null = null;
  for (let i = 0; i < draft.obstacles.length; i++) {
    const o = draft.obstacles[i];
    const halfW = o.width / 2;
    const halfH = o.height / 2;
    if (Math.abs(wx - o.x) <= halfW && Math.abs(wy - o.y) <= halfH) {
      const d = Math.hypot(wx - o.x, wy - o.y);
      if (!best || d < best.d) best = { idx: i, d };
    }
  }
  return best?.idx ?? null;
}

export function moveObstacle(o: ObstacleIn, x: number, y: number): ObstacleIn {
  const next: ObstacleIn = { ...o, x, y };
  if (next.motion?.type === "linear") {
    next.motion = { ...next.motion, x0: x, y0: y };
  } else if (next.motion?.type === "scripted" && next.motion.keyframes.length > 0) {
    const kfs = next.motion.keyframes.map((k, i) => (i === 0 ? { ...k, x, y } : k));
    next.motion = { ...next.motion, keyframes: kfs };
  }
  return next;
}

export function snapCoord(v: number, step = 0.5): number {
  return Math.round(v / step) * step;
}
