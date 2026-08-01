import { useEffect, useRef } from "react";
import { adStateZh, MANEUVER_ZH, ROAD_CLASS_ZH } from "./labels";
import type { Snapshot } from "./types";

const PAD = 12;
const TRAIL_MAX = 100;

function colorForLimit(v: number, vMin: number, vMax: number): string {
  const t = vMax <= vMin + 1e-9 ? 0.5 : Math.max(0, Math.min(1, (v - vMin) / (vMax - vMin)));
  const r = Math.round(214 + (44 - 214) * t);
  const g = Math.round(39 + (160 - 39) * t);
  const b = Math.round(40 + (44 - 40) * t);
  return `rgb(${r},${g},${b})`;
}

/** 后轴中心为原点的车体矩形（+x 朝车头） */
function egoFootprint(
  x: number,
  y: number,
  yaw: number,
  length = 4.8,
  width = 2.5,
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

interface Props {
  snapshot: Snapshot | null;
  paused: boolean;
}

export function BirdEyeCanvas({ snapshot, paused }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const trailRef = useRef<[number, number][]>([]);
  const trailEstRef = useRef<[number, number][]>([]);
  const lastT = useRef(-1);

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

    const xs: number[] = [snapshot.vehicle.x];
    const ys: number[] = [snapshot.vehicle.y];
    for (const [x, y] of snapshot.path || []) {
      xs.push(x);
      ys.push(y);
    }
    for (const link of snapshot.route_links || []) {
      for (const [x, y] of link.points) {
        xs.push(x);
        ys.push(y);
      }
    }
    for (const side of [snapshot.lane_left, snapshot.lane_right]) {
      for (const [x, y] of side || []) {
        xs.push(x);
        ys.push(y);
      }
    }
    for (const o of snapshot.obstacles || []) {
      xs.push(o.x - o.width / 2, o.x + o.width / 2);
      ys.push(o.y - o.height / 2, o.y + o.height / 2);
    }
    const xmin = Math.min(...xs) - PAD;
    const xmax = Math.max(...xs) + PAD;
    const ymin = Math.min(...ys) - PAD;
    const ymax = Math.max(...ys) + PAD;
    const worldW = Math.max(1e-3, xmax - xmin);
    const worldH = Math.max(1e-3, ymax - ymin);
    const scale = Math.min(cssW / worldW, cssH / worldH) * 0.9;
    const ox = (cssW - worldW * scale) / 2;
    const oy = (cssH - worldH * scale) / 2;

    const tx = (x: number) => ox + (x - xmin) * scale;
    const ty = (y: number) => cssH - (oy + (y - ymin) * scale);

    ctx.strokeStyle = "rgba(148,163,184,0.12)";
    ctx.lineWidth = 1;
    for (let gx = Math.floor(xmin / 10) * 10; gx <= xmax; gx += 10) {
      ctx.beginPath();
      ctx.moveTo(tx(gx), ty(ymin));
      ctx.lineTo(tx(gx), ty(ymax));
      ctx.stroke();
    }
    for (let gy = Math.floor(ymin / 10) * 10; gy <= ymax; gy += 10) {
      ctx.beginPath();
      ctx.moveTo(tx(xmin), ty(gy));
      ctx.lineTo(tx(xmax), ty(gy));
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
        if (i === 0) ctx.moveTo(tx(x), ty(y));
        else ctx.lineTo(tx(x), ty(y));
      });
      ctx.stroke();
      ctx.setLineDash([]);

      const [mx, my] = midPoint(link.points as [number, number][]);
      const road = ROAD_CLASS_ZH[link.road_class || "main"] || "主路";
      const man = MANEUVER_ZH[link.maneuver || "straight"] || "";
      const title = link.name || link.link_id;
      const label = `${title} · ${road}/${man} · ${link.speed_limit}m/s`;
      ctx.font = "600 11px 'DM Sans', 'PingFang SC', sans-serif";
      const tw = ctx.measureText(label).width;
      const lx = tx(mx) - tw / 2;
      const ly = ty(my) - 8;
      ctx.fillStyle = "rgba(15,20,25,0.75)";
      ctx.fillRect(lx - 4, ly - 12, tw + 8, 18);
      ctx.fillStyle = "#f8fafc";
      ctx.fillText(label, lx, ly);
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
        if (i === 0) ctx.moveTo(tx(x), ty(y));
        else ctx.lineTo(tx(x), ty(y));
      });
      ctx.stroke();
      ctx.setLineDash([]);
    };

    drawPolyLine(snapshot.lane_left as [number, number][] | undefined, "rgba(148,163,184,0.75)", 1.2);
    drawPolyLine(snapshot.lane_right as [number, number][] | undefined, "rgba(148,163,184,0.75)", 1.2);
    drawPolyLine(snapshot.path as [number, number][] | undefined, "rgba(96,165,250,0.85)", 1.5);

    const drawTrail = (pts: [number, number][], color: string, dash?: number[]) => {
      if (pts.length < 2) return;
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.2;
      ctx.setLineDash(dash || []);
      ctx.beginPath();
      pts.forEach(([x, y], i) => {
        if (i === 0) ctx.moveTo(tx(x), ty(y));
        else ctx.lineTo(tx(x), ty(y));
      });
      ctx.stroke();
      ctx.setLineDash([]);
    };
    drawTrail(trailRef.current, "rgba(251,146,60,0.75)");
    drawTrail(trailEstRef.current, "rgba(34,211,238,0.8)", [6, 4]);

    for (const o of snapshot.obstacles || []) {
      ctx.fillStyle = "rgba(196,156,148,0.55)";
      ctx.strokeStyle = "#8c564b";
      ctx.lineWidth = 1;
      const x0 = tx(o.x - o.width / 2);
      const y0 = ty(o.y + o.height / 2);
      ctx.fillRect(x0, y0, o.width * scale, o.height * scale);
      ctx.strokeRect(x0, y0, o.width * scale, o.height * scale);
    }

    for (const pred of snapshot.predictions || []) {
      const traj = pred.trajectory || [];
      if (traj.length < 2) continue;
      ctx.strokeStyle = "rgba(167,139,250,0.85)";
      ctx.lineWidth = 1.4;
      ctx.setLineDash([5, 4]);
      ctx.beginPath();
      traj.forEach(([x, y], i) => {
        if (i === 0) ctx.moveTo(tx(x), ty(y));
        else ctx.lineTo(tx(x), ty(y));
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
      ctx.beginPath();
      ctx.arc(tx(f.x), ty(f.y), 5, 0, Math.PI * 2);
      ctx.stroke();
    }

    if (snapshot.lookahead) {
      const [lx, ly] = snapshot.lookahead;
      ctx.fillStyle = "#f472b6";
      ctx.beginPath();
      ctx.arc(tx(lx), ty(ly), 5, 0, Math.PI * 2);
      ctx.fill();
    }

    const geom = snapshot.vehicle_geom;
    const vLen = geom?.length ?? 4.8;
    const vWid = geom?.width ?? 2.5;
    const vRear = geom?.rear_overhang ?? 1.0;
    const laneW = snapshot.lane_width ?? geom?.lane_width ?? 3.2;

    const drawEgo = (
      x: number,
      y: number,
      yaw: number,
      fill: string,
      stroke: string,
      dashed = false
    ) => {
      const poly = egoFootprint(x, y, yaw, vLen, vWid, vRear);
      ctx.beginPath();
      poly.forEach(([px, py], i) => {
        if (i === 0) ctx.moveTo(tx(px), ty(py));
        else ctx.lineTo(tx(px), ty(py));
      });
      ctx.closePath();
      ctx.fillStyle = fill;
      ctx.strokeStyle = stroke;
      ctx.lineWidth = 1.5;
      ctx.setLineDash(dashed ? [4, 3] : []);
      if (!dashed) ctx.fill();
      ctx.stroke();
      ctx.setLineDash([]);
      // 后轴中心标记（贴车道中心线）
      ctx.strokeStyle = stroke;
      ctx.lineWidth = 1.5;
      const r = 4;
      ctx.beginPath();
      ctx.moveTo(tx(x) - r, ty(y));
      ctx.lineTo(tx(x) + r, ty(y));
      ctx.moveTo(tx(x), ty(y) - r);
      ctx.lineTo(tx(x), ty(y) + r);
      ctx.stroke();
    };

    const v = snapshot.vehicle;
    drawEgo(v.x, v.y, v.yaw, "rgba(251,191,36,0.85)", "#fb923c");
    if (snapshot.vehicle_est) {
      const e = snapshot.vehicle_est;
      drawEgo(e.x, e.y, e.yaw, "transparent", "#22d3ee", true);
    }

    const limit =
      snapshot.speed_limit == null ? "无" : `${snapshot.speed_limit.toFixed(1)} m/s`;
    const lines = [
      `时间 ${snapshot.t.toFixed(2)} s · 自动驾驶 ${adStateZh(snapshot.state)}${paused ? " · 【已暂停】" : ""}`,
      `车速 ${v.speed.toFixed(2)} · 目标速 ${snapshot.v_cmd.toFixed(2)} · 限速 ${limit}`,
      `转角 ${((snapshot.steer * 180) / Math.PI).toFixed(1)}° · 后轴 (${v.x.toFixed(1)}, ${v.y.toFixed(1)})`,
      `车道宽 ${laneW.toFixed(1)} m · 车宽 ${vWid.toFixed(1)} m · 参考点=后轴中心`,
    ];
    ctx.fillStyle = "rgba(15,20,25,0.78)";
    ctx.fillRect(12, 12, 440, 88);
    ctx.fillStyle = "#e2e8f0";
    ctx.font = "500 12px 'IBM Plex Mono', 'PingFang SC', monospace";
    lines.forEach((line, i) => ctx.fillText(line, 22, 34 + i * 18));

    const legend = [
      "灰线=车道边界(宽3.2m)",
      "中心线跟踪·后轴贴中线",
      "橙框=真值车(宽2.5m)",
      "青虚线=估计  十字=后轴",
    ];
    ctx.fillStyle = "rgba(15,20,25,0.72)";
    ctx.fillRect(12, cssH - 92, 210, 80);
    ctx.fillStyle = "#cbd5e1";
    ctx.font = "500 11px 'DM Sans', 'PingFang SC', sans-serif";
    legend.forEach((line, i) => ctx.fillText(line, 22, cssH - 72 + i * 16));
  }, [snapshot, paused]);

  return <canvas ref={canvasRef} className="bird-eye" />;
}
