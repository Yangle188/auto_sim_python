import type { PresetMeta, SceneConfig, StatusPayload } from "./types";

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

export async function postControl(
  action: "start" | "pause" | "resume" | "reset"
): Promise<StatusPayload> {
  const data = await jsonOrThrow(
    await fetch("/api/control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    })
  );
  return data.status as StatusPayload;
}

export function simWsUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws/sim`;
}
