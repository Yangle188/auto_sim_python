import { useEffect, useRef, useState } from "react";
import { adStateZh, MANEUVER_ZH, ROAD_CLASS_ZH } from "./labels";
import {
  baseMapBounds,
  draftBounds,
  hitObstacle,
  hitWaypoint,
  moveObstacle,
  nearestBaseNode,
  nearestOnPolyline,
  snapCoord,
  type EditTool,
} from "./sceneEdit";
import type { BaseMapData, Point, SceneConfig, Snapshot } from "./types";

const TRAIL_MAX = 100;
/** 车头向上基础视野（m）：前 / 后 / 侧；实际视野 = 基础 / zoom */
const VIEW_AHEAD = 55;
const VIEW_BEHIND = 18;
const VIEW_SIDE = 22;

const ZOOM_MIN = 0.6;
const ZOOM_MAX = 3.5;
const ZOOM_STEP = 0.15;

function colorForLimit(v: number, vMin: number, vMax: number): string {
  const t = vMax <= vMin + 1e-9 ? 0.5 : Math.max(0, Math.min(1, (v - vMin) / (vMax - vMin)));
  const r = Math.round(214 + (44 - 214) * t);
  const g = Math.round(39 + (160 - 39) * t);
  const b = Math.round(40 + (44 - 40) * t);
  return `rgb(${r},${g},${b})`;
}

/** 路径最近点处切向 = 道路前进方向（车道线朝向固定，不跟自车航向抖） */
function pathTangentYaw(path: Point[] | undefined, x: number, y: number): number | null {
  if (!path || path.length < 2) return null;
  let bestI = 0;
  let bestD = Infinity;
  for (let i = 0; i < path.length; i++) {
    const d = Math.hypot(path[i][0] - x, path[i][1] - y);
    if (d < bestD) {
      bestD = d;
      bestI = i;
    }
  }
  const i0 = Math.min(bestI, path.length - 2);
  const dx = path[i0 + 1][0] - path[i0][0];
  const dy = path[i0 + 1][1] - path[i0][1];
  if (Math.hypot(dx, dy) < 1e-9) return null;
  return Math.atan2(dy, dx);
}

/** 后轴中心为原点的车体矩形（+x 朝车头） */
function egoFootprint(
  x: number,
  y: number,
  yaw: number,
  length = 4.8,
  width = 1.96,
  rearOverhang = 1.0
): [number, number][] {
  const xRear = -rearOverhang;
  const xFront = length - rearOverhang;
  const halfW = 0.5 * width;
  const local: [number, number][] = [
    [xFront, halfW],
    [xFront, -halfW],
    [xRear, -halfW],
    [xRear, halfW],
  ];
  const c = Math.cos(yaw);
  const s = Math.sin(yaw);
  return local.map(([lx, ly]) => [x + c * lx - s * ly, y + s * lx + c * ly]);
}

function midPoint(points: [number, number][]): [number, number] {
  let total = 0;
  const seg: number[] = [0];
  for (let i = 0; i < points.length - 1; i++) {
    const d = Math.hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1]);
    total += d;
    seg.push(total);
  }
  const half = total / 2;
  for (let i = 0; i < points.length - 1; i++) {
    if (seg[i + 1] >= half) {
      const t = (half - seg[i]) / Math.max(1e-9, seg[i + 1] - seg[i]);
      return [
        points[i][0] + t * (points[i + 1][0] - points[i][0]),
        points[i][1] + t * (points[i + 1][1] - points[i][1]),
      ];
    }
  }
  return points[Math.floor(points.length / 2)];
}

function clampZoom(z: number): number {
  return Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, z));
}

type DragState =
  | { kind: "waypoint"; linkIdx: number; pointIdx: number }
  | { kind: "obstacle"; idx: number }
  | { kind: "pan"; ox: number; oy: number; panX0: number; panY0: number };

interface Props {
  snapshot: Snapshot | null;
  paused: boolean;
  draft: SceneConfig;
  editTool: EditTool;
  selectedLinkIdx: number;
  selectedObstacleIdx: number | null;
  onChangeDraft: (next: SceneConfig) => void;
  onSelectLink: (idx: number) => void;
  onSelectObstacle: (idx: number | null) => void;
  baseMap: BaseMapData | null;
  navStart: string | null;
  navEnd: string | null;
  onNavPick: (nodeId: string) => void;
}

export function BirdEyeCanvas({
  snapshot,
  paused,
  draft,
  editTool,
  selectedLinkIdx,
  selectedObstacleIdx,
  onChangeDraft,
  onSelectLink,
  onSelectObstacle,
  baseMap,
  navStart,
  navEnd,
  onNavPick,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const trailRef = useRef<[number, number][]>([]);
  const trailEstRef = useRef<[number, number][]>([]);
  const lastT = useRef(-1);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const panRef = useRef(pan);
  const dragRef = useRef<DragState | null>(null);
  const draftRef = useRef(draft);
  const toolRef = useRef(editTool);
  const linkRef = useRef(selectedLinkIdx);
  const baseMapRef = useRef(baseMap);
  const onNavPickRef = useRef(onNavPick);
  panRef.current = pan;
  const xformRef = useRef<{
    screenToWorld: (sx: number, sy: number) => Point;
    metersPerPx: number;
  } | null>(null);

  draftRef.current = draft;
  toolRef.current = editTool;
  linkRef.current = selectedLinkIdx;
  baseMapRef.current = baseMap;
  onNavPickRef.current = onNavPick;

  const editing = editTool !== "none";

  useEffect(() => {
    if (!snapshot) return;
    if (snapshot.t < lastT.current) {
      trailRef.current = [];
      trailEstRef.current = [];
    }
    lastT.current = snapshot.t;
    const v = snapshot.vehicle;
    trailRef.current.push([v.x, v.y]);
    if (trailRef.current.length > TRAIL_MAX) trailRef.current.shift();
    if (snapshot.vehicle_est) {
      trailEstRef.current.push([snapshot.vehicle_est.x, snapshot.vehicle_est.y]);
      if (trailEstRef.current.length > TRAIL_MAX) trailEstRef.current.shift();
    }
  }, [snapshot]);

  useEffect(() => {
    if (editing) setPan({ x: 0, y: 0 });
  }, [editing, draft.route_id]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const dir = e.deltaY > 0 ? -1 : 1;
      setZoom((z) => clampZoom(z + dir * ZOOM_STEP));
    };
    canvas.addEventListener("wheel", onWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", onWheel);
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const clientToLocal = (e: PointerEvent): [number, number] => {
      const rect = canvas.getBoundingClientRect();
      return [e.clientX - rect.left, e.clientY - rect.top];
    };

    const onDown = (e: PointerEvent) => {
      if (!editing || !xformRef.current) return;
      const [sx, sy] = clientToLocal(e);
      const [wx, wy] = xformRef.current.screenToWorld(sx, sy);
      const hitR = Math.max(1.2, 10 * xformRef.current.metersPerPx);
      const d = draftRef.current;
      const tool = toolRef.current;

      if (e.button === 1 || (e.button === 0 && e.altKey)) {
        dragRef.current = {
          kind: "pan",
          ox: sx,
          oy: sy,
          panX0: panRef.current.x,
          panY0: panRef.current.y,
        };
        canvas.setPointerCapture(e.pointerId);
        e.preventDefault();
        return;
      }
      if (e.button !== 0) return;

      if (tool === "nav") {
        const bm = baseMapRef.current;
        if (!bm) return;
        const hitR = Math.max(4, 16 * xformRef.current.metersPerPx);
        const nid = nearestBaseNode(bm, wx, wy, hitR);
        if (nid) {
          onNavPickRef.current(nid);
          e.preventDefault();
        }
        return;
      }

      if (tool === "route") {
        const wp = hitWaypoint(d, wx, wy, hitR);
        if (wp) {
          onSelectLink(wp.linkIdx);
          dragRef.current = { kind: "waypoint", ...wp };
          canvas.setPointerCapture(e.pointerId);
          e.preventDefault();
          return;
        }
        const li = Math.max(0, Math.min(linkRef.current, d.links.length - 1));
        const link = d.links[li];
        if (!link) return;
        const near = nearestOnPolyline(link.points, wx, wy);
        const insertThresh = Math.max(3, 18 * xformRef.current.metersPerPx);
        const nx = snapCoord(wx);
        const ny = snapCoord(wy);
        let points: Point[];
        if (near.dist < insertThresh && near.t > 0.05 && near.t < 0.95) {
          points = [
            ...link.points.slice(0, near.seg + 1),
            [snapCoord(near.px), snapCoord(near.py)],
            ...link.points.slice(near.seg + 1),
          ];
          dragRef.current = { kind: "waypoint", linkIdx: li, pointIdx: near.seg + 1 };
        } else {
          points = [...link.points, [nx, ny]];
          dragRef.current = { kind: "waypoint", linkIdx: li, pointIdx: points.length - 1 };
        }
        const links = d.links.map((l, i) => (i === li ? { ...l, points } : l));
        onChangeDraft({ ...d, links });
        canvas.setPointerCapture(e.pointerId);
        e.preventDefault();
        return;
      }

      if (tool === "obstacle") {
        const oi = hitObstacle(d, wx, wy);
        if (oi != null) {
          onSelectObstacle(oi);
          dragRef.current = { kind: "obstacle", idx: oi };
          canvas.setPointerCapture(e.pointerId);
          e.preventDefault();
          return;
        }
        const nx = snapCoord(wx);
        const ny = snapCoord(wy);
        const obstacles = [
          ...d.obstacles,
          { x: nx, y: ny, width: 2, height: 2, dynamic: false, motion: null },
        ];
        onChangeDraft({ ...d, obstacles });
        onSelectObstacle(obstacles.length - 1);
        dragRef.current = { kind: "obstacle", idx: obstacles.length - 1 };
        canvas.setPointerCapture(e.pointerId);
        e.preventDefault();
      }
    };

    const onMove = (e: PointerEvent) => {
      const drag = dragRef.current;
      if (!drag || !xformRef.current) return;
      const [sx, sy] = clientToLocal(e);
      if (drag.kind === "pan") {
        const mpp = xformRef.current.metersPerPx;
        setPan({
          x: drag.panX0 + (sx - drag.ox) * mpp,
          y: drag.panY0 - (sy - drag.oy) * mpp,
        });
        return;
      }
      const [wx, wy] = xformRef.current.screenToWorld(sx, sy);
      const nx = snapCoord(wx);
      const ny = snapCoord(wy);
      const d = draftRef.current;
      if (drag.kind === "waypoint") {
        const links = d.links.map((l, i) => {
          if (i !== drag.linkIdx) return l;
          const points = l.points.map((p, j) => (j === drag.pointIdx ? ([nx, ny] as Point) : p));
          return { ...l, points };
        });
        onChangeDraft({ ...d, links });
      } else if (drag.kind === "obstacle") {
        const obstacles = d.obstacles.map((o, i) =>
          i === drag.idx ? moveObstacle(o, nx, ny) : o
        );
        onChangeDraft({ ...d, obstacles });
      }
    };

    const onUp = (e: PointerEvent) => {
      if (dragRef.current) {
        dragRef.current = null;
        try {
          canvas.releasePointerCapture(e.pointerId);
        } catch {
          /* ignore */
        }
      }
    };

    const onKey = (e: KeyboardEvent) => {
      if (!editing) return;
      if (e.key !== "Backspace" && e.key !== "Delete") return;
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      const d = draftRef.current;
      const tool = toolRef.current;
      if (tool === "obstacle" && selectedObstacleIdx != null) {
        e.preventDefault();
        onChangeDraft({
          ...d,
          obstacles: d.obstacles.filter((_, i) => i !== selectedObstacleIdx),
        });
        onSelectObstacle(null);
        return;
      }
      if (tool === "route") {
        const li = linkRef.current;
        const link = d.links[li];
        if (!link || link.points.length <= 2) return;
        e.preventDefault();
        const points = link.points.slice(0, -1);
        const links = d.links.map((l, i) => (i === li ? { ...l, points } : l));
        onChangeDraft({ ...d, links });
      }
    };

    canvas.addEventListener("pointerdown", onDown);
    canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("pointerup", onUp);
    canvas.addEventListener("pointercancel", onUp);
    window.addEventListener("keydown", onKey);
    return () => {
      canvas.removeEventListener("pointerdown", onDown);
      canvas.removeEventListener("pointermove", onMove);
      canvas.removeEventListener("pointerup", onUp);
      canvas.removeEventListener("pointercancel", onUp);
      window.removeEventListener("keydown", onKey);
    };
  }, [editing, onChangeDraft, onSelectLink, onSelectObstacle, selectedObstacleIdx]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const cssW = canvas.clientWidth;
    const cssH = canvas.clientHeight;
    canvas.width = Math.max(1, Math.floor(cssW * dpr));
    canvas.height = Math.max(1, Math.floor(cssH * dpr));
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const grad = ctx.createLinearGradient(0, 0, cssW, cssH);
    grad.addColorStop(0, "#0f1419");
    grad.addColorStop(0.55, "#1a2332");
    grad.addColorStop(1, "#243044");
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, cssW, cssH);

    if (!snapshot && !editing) {
      ctx.fillStyle = "rgba(230,236,245,0.7)";
      ctx.font = "500 16px 'DM Sans', 'PingFang SC', sans-serif";
      ctx.fillText("等待仿真画面… 请点击「开始」，或切换到「编路线 / 放障碍」", 24, 40);
      xformRef.current = null;
      return;
    }

    let txy: (wx: number, wy: number) => [number, number];
    let screenToWorld: (sx: number, sy: number) => Point;
    let metersPerPx: number;
    let cx: number;
    let cy: number;

    if (editing) {
      const b =
        editTool === "nav" && baseMap ? baseMapBounds(baseMap) : draftBounds(draft);
      const worldW = (b.maxX - b.minX) / zoom;
      const worldH = (b.maxY - b.minY) / zoom;
      const scale = Math.min(cssW / worldW, cssH / worldH) * 0.92;
      metersPerPx = 1 / scale;
      const midX = (b.minX + b.maxX) / 2 - pan.x;
      const midY = (b.minY + b.maxY) / 2 - pan.y;
      cx = cssW / 2;
      cy = cssH / 2;
      txy = (wx, wy) => [cx + (wx - midX) * scale, cy - (wy - midY) * scale];
      screenToWorld = (sx, sy) => [
        midX + (sx - cx) * metersPerPx,
        midY - (sy - cy) * metersPerPx,
      ];
    } else {
      const ego = snapshot!.vehicle;
      const camYaw = pathTangentYaw(snapshot!.path, ego.x, ego.y) ?? ego.yaw;
      const camX = ego.x;
      const camY = ego.y;
      const c = Math.cos(camYaw);
      const s = Math.sin(camYaw);
      const ahead = VIEW_AHEAD / zoom;
      const behind = VIEW_BEHIND / zoom;
      const side = VIEW_SIDE / zoom;
      const worldW = side * 2;
      const worldH = ahead + behind;
      const scale = Math.min(cssW / worldW, cssH / worldH) * 0.92;
      metersPerPx = 1 / scale;
      cx = cssW / 2;
      cy = cssH * (ahead / worldH);
      txy = (wx, wy) => {
        const dx = wx - camX;
        const dy = wy - camY;
        const fwd = c * dx + s * dy;
        const left = -s * dx + c * dy;
        return [cx + left * scale, cy - fwd * scale];
      };
      screenToWorld = (sx, sy) => {
        const left = (sx - cx) * metersPerPx;
        const fwd = (cy - sy) * metersPerPx;
        return [camX + c * fwd - s * left, camY + s * fwd + c * left];
      };
    }
    xformRef.current = { screenToWorld, metersPerPx };

    // grid
    if (editing) {
      const b =
        editTool === "nav" && baseMap ? baseMapBounds(baseMap) : draftBounds(draft);
      const step = zoom >= 2 ? 2.5 : 5;
      ctx.strokeStyle = "rgba(148,163,184,0.12)";
      ctx.lineWidth = 1;
      const x0 = Math.floor(b.minX / step) * step;
      const y0 = Math.floor(b.minY / step) * step;
      for (let x = x0; x <= b.maxX + 1e-6; x += step) {
        const a = txy(x, b.minY);
        const bb = txy(x, b.maxY);
        ctx.beginPath();
        ctx.moveTo(a[0], a[1]);
        ctx.lineTo(bb[0], bb[1]);
        ctx.stroke();
      }
      for (let y = y0; y <= b.maxY + 1e-6; y += step) {
        const a = txy(b.minX, y);
        const bb = txy(b.maxX, y);
        ctx.beginPath();
        ctx.moveTo(a[0], a[1]);
        ctx.lineTo(bb[0], bb[1]);
        ctx.stroke();
      }
    } else if (snapshot) {
      const ego = snapshot.vehicle;
      const camYaw = pathTangentYaw(snapshot.path, ego.x, ego.y) ?? ego.yaw;
      const camX = ego.x;
      const camY = ego.y;
      const c = Math.cos(camYaw);
      const s = Math.sin(camYaw);
      const ahead = VIEW_AHEAD / zoom;
      const behind = VIEW_BEHIND / zoom;
      const side = VIEW_SIDE / zoom;
      const gridStep = zoom >= 2 ? 2.5 : 5;
      ctx.strokeStyle = "rgba(148,163,184,0.12)";
      ctx.lineWidth = 1;
      for (let lat = -side; lat <= side + 1e-6; lat += gridStep) {
        const a = txy(camX + c * -behind - s * lat, camY + s * -behind + c * lat);
        const b = txy(camX + c * ahead - s * lat, camY + s * ahead + c * lat);
        ctx.beginPath();
        ctx.moveTo(a[0], a[1]);
        ctx.lineTo(b[0], b[1]);
        ctx.stroke();
      }
    }

    const drawPolyLine = (
      pts: [number, number][] | undefined,
      color: string,
      width: number,
      dash?: number[]
    ) => {
      if (!pts || pts.length < 2) return;
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.setLineDash(dash || []);
      ctx.beginPath();
      pts.forEach(([x, y], i) => {
        const [px, py] = txy(x, y);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      });
      ctx.stroke();
      ctx.setLineDash([]);
    };

    const drawMarkings = (
      markings: { style?: string; points: Point[] }[] | undefined,
      solidColor: string,
      dashColor: string,
      solidW: number,
      dashW: number
    ) => {
      if (!markings) return;
      for (const m of markings) {
        const dashed = m.style === "dashed";
        drawPolyLine(
          m.points as [number, number][],
          dashed ? dashColor : solidColor,
          dashed ? dashW : solidW,
          dashed ? [10, 8] : undefined
        );
      }
    };

    // 底图全网车道线（算路相关场景）；导航路径车道线稍后更亮叠画
    if (editing && baseMap && (editTool === "nav" || draft.base_map_id === baseMap.map_id)) {
      drawMarkings(
        baseMap.lane_markings,
        "rgba(148,163,184,0.55)",
        "rgba(148,163,184,0.28)",
        1.4,
        1.0
      );
    } else if (!editing && snapshot?.network_lane_markings?.length) {
      drawMarkings(
        snapshot.network_lane_markings,
        "rgba(148,163,184,0.45)",
        "rgba(148,163,184,0.22)",
        1.3,
        0.9
      );
    }

    if (editing && editTool === "nav" && baseMap) {
      for (const n of baseMap.nodes) {
        const [px, py] = txy(n.x, n.y);
        const isStart = n.node_id === navStart;
        const isEnd = n.node_id === navEnd;
        ctx.fillStyle = isStart ? "#34d399" : isEnd ? "#f87171" : "rgba(96,165,250,0.9)";
        ctx.strokeStyle = "#0f1419";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(px, py, isStart || isEnd ? 8 : 6, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = "#e2e8f0";
        ctx.font = "600 10px 'DM Sans', 'PingFang SC', sans-serif";
        ctx.fillText(n.name || n.node_id, px + 9, py - 8);
      }
    }

    const routeLinks = editing ? draft.links : snapshot?.route_links || [];
    const limits = routeLinks.map((l) => l.speed_limit);
    const vMin = limits.length ? Math.min(...limits) : 0;
    const vMax = limits.length ? Math.max(...limits) : 1;

    for (let li = 0; li < routeLinks.length; li++) {
      const link = routeLinks[li];
      if (link.points.length < 2) continue;
      const isAux = (link.road_class || "main") === "aux";
      const selected = editing && li === selectedLinkIdx;
      ctx.strokeStyle = selected ? "#fbbf24" : colorForLimit(link.speed_limit, vMin, vMax);
      ctx.lineWidth = selected ? 4.2 : isAux ? 2.4 : 3.6;
      ctx.setLineDash(isAux && !selected ? [8, 5] : []);
      ctx.beginPath();
      link.points.forEach(([x, y], i) => {
        const [px, py] = txy(x, y);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      });
      ctx.stroke();
      ctx.setLineDash([]);

      const [mx, my] = midPoint(link.points as [number, number][]);
      const [lx, ly] = txy(mx, my);
      if (lx > -40 && lx < cssW + 40 && ly > -20 && ly < cssH + 20) {
        const road = ROAD_CLASS_ZH[link.road_class || "main"] || "主路";
        const man = MANEUVER_ZH[link.maneuver || "straight"] || "";
        const title = link.name || link.link_id;
        const label = `${title} · ${road}/${man} · ${link.speed_limit}m/s`;
        ctx.font = "600 11px 'DM Sans', 'PingFang SC', sans-serif";
        const tw = ctx.measureText(label).width;
        ctx.fillStyle = "rgba(15,20,25,0.75)";
        ctx.fillRect(lx - tw / 2 - 4, ly - 20, tw + 8, 18);
        ctx.fillStyle = selected ? "#fde68a" : "#f8fafc";
        ctx.fillText(label, lx - tw / 2, ly - 8);
      }

      if (editing && editTool === "route") {
        link.points.forEach(([x, y], pi) => {
          const [px, py] = txy(x, y);
          const isSel = selected && pi === link.points.length - 1;
          ctx.fillStyle = selected ? "#fbbf24" : "rgba(148,163,184,0.85)";
          ctx.strokeStyle = "#0f1419";
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.arc(px, py, isSel || selected ? 6 : 4.5, 0, Math.PI * 2);
          ctx.fill();
          ctx.stroke();
        });
      }
    }

    if (!editing && snapshot) {
      // 自车导航路径车道线（更亮，叠在底图路网上）
      const markings = snapshot.lane_markings;
      if (markings && markings.length > 0) {
        drawMarkings(
          markings,
          "rgba(226,232,240,0.95)",
          "rgba(226,232,240,0.65)",
          1.7,
          1.2
        );
      } else {
        drawPolyLine(snapshot.lane_left as [number, number][] | undefined, "rgba(148,163,184,0.75)", 1.2);
        drawPolyLine(snapshot.lane_right as [number, number][] | undefined, "rgba(148,163,184,0.75)", 1.2);
      }
      drawPolyLine(snapshot.path as [number, number][] | undefined, "rgba(96,165,250,0.85)", 1.5);

      const drawTrail = (pts: [number, number][], color: string, dash?: number[]) => {
        if (pts.length < 2) return;
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.2;
        ctx.setLineDash(dash || []);
        ctx.beginPath();
        pts.forEach(([x, y], i) => {
          const [px, py] = txy(x, y);
          if (i === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        });
        ctx.stroke();
        ctx.setLineDash([]);
      };
      drawTrail(trailRef.current, "rgba(251,146,60,0.75)");
      drawTrail(trailEstRef.current, "rgba(34,211,238,0.8)", [6, 4]);
    }

    const obstacles = editing
      ? draft.obstacles
      : (snapshot?.obstacles || []).map((o) => ({
          ...o,
          dynamic: false,
          motion: null,
        }));

    for (let oi = 0; oi < obstacles.length; oi++) {
      const o = obstacles[oi];
      const selected = editing && oi === selectedObstacleIdx;
      const corners: [number, number][] = [
        [o.x - o.width / 2, o.y - o.height / 2],
        [o.x + o.width / 2, o.y - o.height / 2],
        [o.x + o.width / 2, o.y + o.height / 2],
        [o.x - o.width / 2, o.y + o.height / 2],
      ];
      ctx.fillStyle = selected ? "rgba(251,191,36,0.45)" : "rgba(196,156,148,0.55)";
      ctx.strokeStyle = selected ? "#fbbf24" : "#8c564b";
      ctx.lineWidth = selected ? 2 : 1;
      ctx.beginPath();
      corners.forEach(([x, y], i) => {
        const [px, py] = txy(x, y);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      });
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      if (editing && "dynamic" in o && o.dynamic) {
        const [cxo, cyo] = txy(o.x, o.y);
        ctx.fillStyle = "#93c5fd";
        ctx.font = "600 10px 'DM Sans', 'PingFang SC', sans-serif";
        ctx.fillText("动", cxo - 5, cyo + 3);
      }
    }

    if (!editing && snapshot) {
      for (const pred of snapshot.predictions || []) {
        const traj = pred.trajectory || [];
        if (traj.length < 2) continue;
        ctx.strokeStyle = "rgba(167,139,250,0.85)";
        ctx.lineWidth = 1.4;
        ctx.setLineDash([5, 4]);
        ctx.beginPath();
        traj.forEach(([x, y], i) => {
          const [px, py] = txy(x, y);
          if (i === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        });
        ctx.stroke();
        ctx.setLineDash([]);
      }

      for (const f of snapshot.fused || []) {
        const color =
          f.source === "fusion"
            ? "#ef4444"
            : f.source === "lidar_only"
              ? "#3b82f6"
              : f.source === "camera_only"
                ? "#22c55e"
                : "#a78bfa";
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        const [fx, fy] = txy(f.x, f.y);
        ctx.beginPath();
        ctx.arc(fx, fy, 5, 0, Math.PI * 2);
        ctx.stroke();
      }

      if (snapshot.lookahead) {
        const [lx, ly] = snapshot.lookahead;
        const [px, py] = txy(lx, ly);
        ctx.fillStyle = "#f472b6";
        ctx.beginPath();
        ctx.arc(px, py, 5, 0, Math.PI * 2);
        ctx.fill();
      }

      const geom = snapshot.vehicle_geom;
      const vLen = geom?.length ?? 4.8;
      const vWid = geom?.width ?? 1.96;
      const vRear = geom?.rear_overhang ?? 1.0;
      const ego = snapshot.vehicle;

      const drawEgo = (
        x: number,
        y: number,
        yawVeh: number,
        fill: string,
        stroke: string,
        dashed = false
      ) => {
        const poly = egoFootprint(x, y, yawVeh, vLen, vWid, vRear);
        ctx.beginPath();
        poly.forEach(([px, py], i) => {
          const [sx, sy] = txy(px, py);
          if (i === 0) ctx.moveTo(sx, sy);
          else ctx.lineTo(sx, sy);
        });
        ctx.closePath();
        ctx.fillStyle = fill;
        ctx.strokeStyle = stroke;
        ctx.lineWidth = 1.5;
        ctx.setLineDash(dashed ? [4, 3] : []);
        if (!dashed) ctx.fill();
        ctx.stroke();
        ctx.setLineDash([]);
        const [ax, ay] = txy(x, y);
        ctx.strokeStyle = stroke;
        ctx.lineWidth = 1.5;
        const r = 4;
        ctx.beginPath();
        ctx.moveTo(ax - r, ay);
        ctx.lineTo(ax + r, ay);
        ctx.moveTo(ax, ay - r);
        ctx.lineTo(ax, ay + r);
        ctx.stroke();
      };

      drawEgo(ego.x, ego.y, ego.yaw, "rgba(251,191,36,0.85)", "#fb923c");
      if (snapshot.vehicle_est) {
        const e = snapshot.vehicle_est;
        const [ex, ey] = txy(e.x, e.y);
        ctx.strokeStyle = "#22d3ee";
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 3]);
        ctx.beginPath();
        ctx.arc(ex, ey, 6, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(ex - 5, ey);
        ctx.lineTo(ex + 5, ey);
        ctx.moveTo(ex, ey - 5);
        ctx.lineTo(ex, ey + 5);
        ctx.stroke();
      }

      ctx.fillStyle = "rgba(251,191,36,0.9)";
      ctx.beginPath();
      ctx.moveTo(cx, cy - 28);
      ctx.lineTo(cx - 5, cy - 18);
      ctx.lineTo(cx + 5, cy - 18);
      ctx.closePath();
      ctx.fill();

      const laneW = snapshot.lane_width ?? geom?.lane_width ?? 3.2;
      const numLanes = snapshot.num_lanes ?? geom?.num_lanes ?? 3;
      const limit =
        snapshot.speed_limit == null ? "无" : `${snapshot.speed_limit.toFixed(1)} m/s`;
      const acc = snapshot.acc;
      const accLine = acc
        ? `ACC 间距 ${acc.d_gap.toFixed(1)}m · 前车 ${acc.v_lead.toFixed(1)}m/s · ${acc.source}`
        : "ACC 无前车（巡航/切出后加速）";
      let lat = 0;
      if (snapshot.path && snapshot.path.length >= 2) {
        let best = Infinity;
        for (let i = 0; i < snapshot.path.length - 1; i++) {
          const [x0, y0] = snapshot.path[i];
          const [x1, y1] = snapshot.path[i + 1];
          const dx = x1 - x0;
          const dy = y1 - y0;
          const L2 = dx * dx + dy * dy;
          const t =
            L2 < 1e-12 ? 0 : Math.max(0, Math.min(1, ((ego.x - x0) * dx + (ego.y - y0) * dy) / L2));
          const d = Math.hypot(ego.x - (x0 + t * dx), ego.y - (y0 + t * dy));
          if (d < best) best = d;
        }
        lat = best;
      }
      const lines = [
        `时间 ${snapshot.t.toFixed(2)} s · 自动驾驶 ${adStateZh(snapshot.state)}${paused ? " · 【已暂停】" : ""}`,
        `车速 ${ego.speed.toFixed(2)} · 目标速 ${snapshot.v_cmd.toFixed(2)} · 限速 ${limit}`,
        accLine,
        `道路朝上 · 横向偏差 ${lat.toFixed(2)}m · 缩放 ${zoom.toFixed(1)}× · ${numLanes}×${laneW.toFixed(1)}m`,
      ];
      ctx.fillStyle = "rgba(15,20,25,0.78)";
      ctx.fillRect(12, 12, 480, 88);
      ctx.fillStyle = "#e2e8f0";
      ctx.font = "500 12px 'IBM Plex Mono', 'PingFang SC', monospace";
      lines.forEach((line, i) => ctx.fillText(line, 22, 34 + i * 18));

      const legend = [
        "车道线=世界(道路朝上)",
        "橙框=自车真值(控制)",
        "青点=定位估计",
        "滚轮/右下角缩放",
      ];
      ctx.fillStyle = "rgba(15,20,25,0.72)";
      ctx.fillRect(12, cssH - 92, 230, 80);
      ctx.fillStyle = "#cbd5e1";
      ctx.font = "500 11px 'DM Sans', 'PingFang SC', sans-serif";
      legend.forEach((line, i) => ctx.fillText(line, 22, cssH - 72 + i * 16));
    } else if (editing) {
      const toolHint =
        editTool === "route"
          ? "编路线：点击追加/插入路点 · 拖拽移动 · Delete 删末点 · Alt 拖动画布"
          : editTool === "obstacle"
            ? "放障碍：空白处点击放置 · 拖拽移动 · Delete 删除选中 · Alt 拖动画布"
            : `算路：依次点选起点/终点节点${navStart ? ` · 起点 ${navStart}` : ""}${navEnd ? ` · 终点 ${navEnd}` : ""} · 将自动规划并写入草稿`;
      ctx.fillStyle = "rgba(15,20,25,0.82)";
      ctx.fillRect(12, 12, Math.min(620, cssW - 24), 52);
      ctx.fillStyle = "#fde68a";
      ctx.font = "600 12px 'DM Sans', 'PingFang SC', sans-serif";
      ctx.fillText(
        editTool === "nav"
          ? `底图算路 · ${baseMap?.title || "路网"}（算完请「应用并重开」）`
          : "场景编辑 · 鸟瞰全图（改完请「应用并重开」）",
        22,
        32
      );
      ctx.fillStyle = "#cbd5e1";
      ctx.font = "500 11px 'DM Sans', 'PingFang SC', sans-serif";
      ctx.fillText(toolHint, 22, 50);
    }
  }, [
    snapshot,
    paused,
    zoom,
    pan,
    editing,
    editTool,
    draft,
    selectedLinkIdx,
    selectedObstacleIdx,
    baseMap,
    navStart,
    navEnd,
  ]);

  return (
    <div className={`bird-eye-wrap${editing ? " editing" : ""}`}>
      <canvas
        ref={canvasRef}
        className="bird-eye"
        style={{
          cursor: editing
            ? editTool === "obstacle"
              ? "crosshair"
              : editTool === "nav"
                ? "pointer"
                : "cell"
            : "default",
        }}
      />
      <div className="zoom-controls" aria-label="缩放">
        <button
          type="button"
          className="zoom-btn"
          title="放大"
          onClick={() => setZoom((z) => clampZoom(z + ZOOM_STEP))}
        >
          +
        </button>
        <button
          type="button"
          className="zoom-btn zoom-label"
          title="重置缩放"
          onClick={() => {
            setZoom(1);
            setPan({ x: 0, y: 0 });
          }}
        >
          {zoom.toFixed(1)}×
        </button>
        <button
          type="button"
          className="zoom-btn"
          title="缩小"
          onClick={() => setZoom((z) => clampZoom(z - ZOOM_STEP))}
        >
          −
        </button>
      </div>
    </div>
  );
}
