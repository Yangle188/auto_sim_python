import type { BaseMapData, PresetMeta, SceneConfig, StatusPayload } from "./types";

async function jsonOrThrow(res: Response) {
  if (!res.ok) {
    const text = await res.text();
    let detail = text || res.statusText;
    try {
      const j = JSON.parse(text);
      if (j.detail) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* keep text */
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function fetchScene(): Promise<{
  draft: SceneConfig;
  applied: SceneConfig;
  status: StatusPayload;
}> {
  return jsonOrThrow(await fetch("/api/scene"));
}

export async function fetchPresets(): Promise<{
  presets: PresetMeta[];
  scenes: Record<string, SceneConfig>;
}> {
  return jsonOrThrow(await fetch("/api/presets"));
}

export async function putScene(scene: SceneConfig): Promise<void> {
  await jsonOrThrow(
    await fetch("/api/scene", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(scene),
    })
  );
}

export type ControlAction =
  | "start"
  | "pause"
  | "resume"
  | "reset"
  | "step_prev"
  | "step_next"
  | "seek"
  | "activate"
  | "deactivate"
  | "lane_change";

export async function postControl(
  action: ControlAction,
  extra?: { frame_i?: number; direction?: "left" | "right" }
): Promise<{ status: StatusPayload; frame?: unknown }> {
  const data = await jsonOrThrow(
    await fetch("/api/control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, ...(extra || {}) }),
    })
  );
  return {
    status: data.status as StatusPayload,
    frame: data.frame,
  };
}

export function simWsUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws/sim`;
}

export async function fetchBasemap(mapId?: string): Promise<BaseMapData> {
  const q = mapId ? `?map_id=${encodeURIComponent(mapId)}` : "";
  return jsonOrThrow(await fetch(`/api/basemap${q}`));
}

export async function postRoutePlan(body: {
  start_node?: string;
  end_node?: string;
  start?: [number, number];
  end?: [number, number];
  duration_s?: number;
  clear_obstacles?: boolean;
  map_id?: string;
}): Promise<{
  ok: boolean;
  length_m: number;
  draft: SceneConfig;
  start_node: string | null;
  end_node: string | null;
}> {
  return jsonOrThrow(
    await fetch("/api/route/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
  );
}
