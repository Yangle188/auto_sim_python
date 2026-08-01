import { useEffect, useRef, useState } from "react";
import { adStateZh, MANEUVER_ZH, ROAD_CLASS_ZH } from "./labels";
import type { Point, Snapshot } from "./types";

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

interface Props {
  snapshot: Snapshot | null;
  paused: boolean;
}

export function BirdEyeCanvas({ snapshot, paused }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const trailRef = useRef<[number, number][]>([]);
  const trailEstRef = useRef<[number, number][]>([]);
  const lastT = useRef(-1);
  const [zoom, setZoom] = useState(1);

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

    if (!snapshot) {
      ctx.fillStyle = "rgba(230,236,245,0.7)";
      ctx.font = "500 16px 'DM Sans', 'PingFang SC', sans-serif";
      ctx.fillText("等待仿真画面… 请点击「开始」", 24, 40);
      return;
    }

    const ego = snapshot.vehicle;
    // 相机朝向 = 路径切向（世界道路朝向），不跟自车 yaw，车道线不因画龙而抖
    const camYaw = pathTangentYaw(snapshot.path, ego.x, ego.y) ?? ego.yaw;
    const camX = ego.x;
    const camY = ego.y;
    const c = Math.cos(camYaw);
    const s = Math.sin(camYaw);

    const toBody = (wx: number, wy: number): [number, number] => {
      const dx = wx - camX;
      const dy = wy - camY;
      const fwd = c * dx + s * dy;
      const left = -s * dx + c * dy;
      return [left, fwd];
    };

    const ahead = VIEW_AHEAD / zoom;
    const behind = VIEW_BEHIND / zoom;
    const side = VIEW_SIDE / zoom;
    const worldW = side * 2;
    const worldH = ahead + behind;
    const scale = Math.min(cssW / worldW, cssH / worldH) * 0.92;
    const cx = cssW / 2;
    const cy = cssH * (ahead / worldH);

    const txy = (wx: number, wy: number): [number, number] => {
      const [left, fwd] = toBody(wx, wy);
      return [cx + left * scale, cy - fwd * scale];
    };

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

    const limits = (snapshot.route_links || []).map((l) => l.speed_limit);
    const vMin = limits.length ? Math.min(...limits) : 0;
    const vMax = limits.length ? Math.max(...limits) : 1;

    for (const link of snapshot.route_links || []) {
      if (link.points.length < 2) continue;
      const isAux = (link.road_class || "main") === "aux";
      ctx.strokeStyle = colorForLimit(link.speed_limit, vMin, vMax);
      ctx.lineWidth = isAux ? 2.4 : 3.6;
      ctx.setLineDash(isAux ? [8, 5] : []);
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
        ctx.fillStyle = "#f8fafc";
        ctx.fillText(label, lx - tw / 2, ly - 8);
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

    const markings = snapshot.lane_markings;
    if (markings && markings.length > 0) {
      for (const m of markings) {
        const dashed = m.style === "dashed";
        drawPolyLine(
          m.points as [number, number][],
          dashed ? "rgba(226,232,240,0.55)" : "rgba(148,163,184,0.9)",
          dashed ? 1.1 : 1.6,
          dashed ? [10, 8] : undefined
        );
      }
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

    for (const o of snapshot.obstacles || []) {
      const corners: [number, number][] = [
        [o.x - o.width / 2, o.y - o.height / 2],
        [o.x + o.width / 2, o.y - o.height / 2],
        [o.x + o.width / 2, o.y + o.height / 2],
        [o.x - o.width / 2, o.y + o.height / 2],
      ];
      ctx.fillStyle = "rgba(196,156,148,0.55)";
      ctx.strokeStyle = "#8c564b";
      ctx.lineWidth = 1;
      ctx.beginPath();
      corners.forEach(([x, y], i) => {
        const [px, py] = txy(x, y);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      });
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
    }

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
    const laneW = snapshot.lane_width ?? geom?.lane_width ?? 3.2;
    const numLanes = snapshot.num_lanes ?? geom?.num_lanes ?? 3;

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

    // 自车用真实航向绘制（可看出相对车道的姿态）；相机不跟 yaw
    drawEgo(ego.x, ego.y, ego.yaw, "rgba(251,191,36,0.85)", "#fb923c");
    if (snapshot.vehicle_est) {
      const e = snapshot.vehicle_est;
      drawEgo(e.x, e.y, e.yaw, "transparent", "#22d3ee", true);
    }

    ctx.strokeStyle = "rgba(251,191,36,0.9)";
    ctx.fillStyle = "rgba(251,191,36,0.9)";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(cx, cy - 28);
    ctx.lineTo(cx - 5, cy - 18);
    ctx.lineTo(cx + 5, cy - 18);
    ctx.closePath();
    ctx.fill();

    const limit =
      snapshot.speed_limit == null ? "无" : `${snapshot.speed_limit.toFixed(1)} m/s`;
    const acc = snapshot.acc;
    const accLine = acc
      ? `ACC 间距 ${acc.d_gap.toFixed(1)}m · 前车 ${acc.v_lead.toFixed(1)}m/s · ${acc.source}`
      : "ACC 无前车（巡航/切出后加速）";
    // 横向偏离：到路径折线最近点的距离
    let lat = 0;
    if (snapshot.path && snapshot.path.length >= 2) {
      let best = Infinity;
      for (let i = 0; i < snapshot.path.length - 1; i++) {
        const [x0, y0] = snapshot.path[i];
        const [x1, y1] = snapshot.path[i + 1];
        const dx = x1 - x0;
        const dy = y1 - y0;
        const L2 = dx * dx + dy * dy;
        const t = L2 < 1e-12 ? 0 : Math.max(0, Math.min(1, ((ego.x - x0) * dx + (ego.y - y0) * dy) / L2));
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
      "车道线=世界(道路朝上固定)",
      "橙框=自车真实姿态",
      "滚轮/右下角缩放",
      "画龙已从控制侧抑制",
    ];
    ctx.fillStyle = "rgba(15,20,25,0.72)";
    ctx.fillRect(12, cssH - 92, 230, 80);
    ctx.fillStyle = "#cbd5e1";
    ctx.font = "500 11px 'DM Sans', 'PingFang SC', sans-serif";
    legend.forEach((line, i) => ctx.fillText(line, 22, cssH - 72 + i * 16));
  }, [snapshot, paused, zoom]);

  return (
    <div className="bird-eye-wrap">
      <canvas ref={canvasRef} className="bird-eye" />
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
          onClick={() => setZoom(1)}
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
