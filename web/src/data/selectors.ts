import type { Point, Snapshot, StatusPayload } from "../types";

/** 点到折线最短距离与横向符号（左正，近似） */
export function lateralErrorM(
  x: number,
  y: number,
  path: Point[] | undefined
): number | null {
  if (!path || path.length < 2) return null;
  let bestD2 = Infinity;
  let bestLat = 0;
  for (let i = 0; i < path.length - 1; i++) {
    const [x0, y0] = path[i];
    const [x1, y1] = path[i + 1];
    const dx = x1 - x0;
    const dy = y1 - y0;
    const L2 = dx * dx + dy * dy;
    if (L2 < 1e-12) continue;
    const t = Math.max(0, Math.min(1, ((x - x0) * dx + (y - y0) * dy) / L2));
    const px = x0 + t * dx;
    const py = y0 + t * dy;
    const d2 = (px - x) ** 2 + (py - y) ** 2;
    if (d2 < bestD2) {
      bestD2 = d2;
      const inv = 1 / Math.sqrt(L2);
      const nx = -dy * inv;
      const ny = dx * inv;
      bestLat = (x - px) * nx + (y - py) * ny;
    }
  }
  if (!Number.isFinite(bestD2)) return null;
  return bestLat;
}

export interface ChannelMetrics {
  speed: number;
  vCmd: number | null;
  accel: number | null;
  steer: number | null;
  dGap: number | null;
  ttc: number | null;
  handsOffS: number | null;
  handsOffWarnS: number;
  handsOffTorS: number;
  latErrM: number | null;
  speedLimit: number | null;
  aebMode: string;
  adState: string;
  accActive: boolean;
  nudgeActive: boolean;
  lcActive: boolean;
  handsOffTracking: boolean;
  handsOffWarned: boolean;
  torPending: boolean;
}

export function selectChannelMetrics(
  frame: Snapshot | null,
  status: StatusPayload
): ChannelMetrics {
  const dms = status.dms ?? frame?.dms;
  const aeb = frame?.aeb;
  const acc = frame?.acc;
  const vehicle = frame?.vehicle;
  const lat =
    vehicle && frame?.path
      ? lateralErrorM(vehicle.x, vehicle.y, frame.path)
      : null;

  return {
    speed: vehicle?.speed ?? 0,
    vCmd: frame?.v_cmd ?? null,
    accel: frame?.accel ?? null,
    steer: frame?.steer ?? null,
    dGap: aeb?.d_gap ?? acc?.d_gap ?? null,
    ttc: aeb?.ttc ?? null,
    handsOffS: dms?.tracking ? dms.hands_off_s ?? 0 : null,
    handsOffWarnS: dms?.hands_off_warn_s ?? 6,
    handsOffTorS: dms?.hands_off_tor_s ?? 12,
    latErrM: lat,
    speedLimit: frame?.speed_limit ?? null,
    aebMode: aeb?.mode ?? "none",
    adState: status.ad_state ?? frame?.state ?? "OFF",
    accActive: !!acc,
    nudgeActive: (status.nudge?.state ?? frame?.nudge?.state) === "nudging",
    lcActive: !!(
      status.lane_change?.state &&
      status.lane_change.state !== "idle"
    ),
    handsOffTracking: !!dms?.tracking,
    handsOffWarned: !!dms?.warned,
    torPending: !!(status.tor_pending ?? frame?.tor_pending),
  };
}
