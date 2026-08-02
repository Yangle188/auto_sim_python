import { useCallback, useEffect, useState } from "react";
import { BirdEyeCanvas } from "./BirdEyeCanvas";
import { ConfigPanel } from "./ConfigPanel";
import {
  fetchBasemap,
  fetchPresets,
  fetchScene,
  postControl,
  postRoutePlan,
  putScene,
  simWsUrl,
} from "./api";
import { statusZh } from "./labels";
import type { EditTool } from "./sceneEdit";
import type { BaseMapData, PresetMeta, SceneConfig, Snapshot, StatusPayload } from "./types";

const EMPTY: SceneConfig = {
  route_id: "custom",
  links: [
    {
      link_id: "L1",
      name: "自定义",
      points: [
        [0, 0],
        [40, 0],
      ],
      speed_limit: 8,
      road_class: "main",
      maneuver: "straight",
    },
  ],
  obstacles: [],
  duration_s: 20,
};

export default function App() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [status, setStatus] = useState<StatusPayload>({
    status: "idle",
    t: 0,
    duration_s: 35,
  });
  const [draft, setDraft] = useState<SceneConfig>(EMPTY);
  const [presets, setPresets] = useState<PresetMeta[]>([]);
  const [scenes, setScenes] = useState<Record<string, SceneConfig>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [wsOk, setWsOk] = useState(false);
  const [editTool, setEditTool] = useState<EditTool>("none");
  const [selectedLinkIdx, setSelectedLinkIdx] = useState(0);
  const [selectedObstacleIdx, setSelectedObstacleIdx] = useState<number | null>(null);
  const [baseMap, setBaseMap] = useState<BaseMapData | null>(null);
  const [navStart, setNavStart] = useState<string | null>(null);
  const [navEnd, setNavEnd] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchScene(), fetchPresets(), fetchBasemap()])
      .then(([sceneData, presetData, bm]) => {
        setDraft(sceneData.draft);
        setStatus(sceneData.status);
        setPresets(presetData.presets);
        setScenes(presetData.scenes);
        setBaseMap(bm);
      })
      .catch((e) => setError(String(e.message || e)));
  }, []);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let closed = false;
    let retry: number | undefined;

    const connect = () => {
      if (closed) return;
      ws = new WebSocket(simWsUrl());
      ws.onopen = () => setWsOk(true);
      ws.onclose = () => {
        setWsOk(false);
        if (!closed) retry = window.setTimeout(connect, 1200);
      };
      ws.onerror = () => ws?.close();
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === "frame") setSnapshot(msg.data as Snapshot);
          if (msg.type === "status") setStatus(msg.data as StatusPayload);
        } catch {
          /* ignore */
        }
      };
    };
    connect();
    return () => {
      closed = true;
      if (retry) window.clearTimeout(retry);
      ws?.close();
    };
  }, []);

  const runControl = useCallback(async (action: "start" | "pause" | "resume" | "reset") => {
    setBusy(true);
    setError(null);
    try {
      const st = await postControl(action);
      setStatus(st);
      if (action === "reset") setSnapshot(null);
    } catch (e) {
      setError(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.code === "Space") {
        e.preventDefault();
        if (status.status === "running") runControl("pause");
        else if (status.status === "paused") runControl("resume");
        else runControl("start");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [status.status, runControl]);

  const onApply = async () => {
    setBusy(true);
    setError(null);
    try {
      await putScene(draft);
      await postControl("reset");
      const st = await postControl("start");
      setStatus(st);
      setSnapshot(null);
      setEditTool("none");
    } catch (e) {
      setError(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  };

  const onLoadPreset = (id: string) => {
    const scene = scenes[id];
    if (scene) {
      setDraft(scene);
      setSelectedLinkIdx(0);
      setSelectedObstacleIdx(scene.obstacles.length ? 0 : null);
      setNavStart(null);
      setNavEnd(null);
      setError(null);
    }
  };

  const onNavPick = useCallback(
    async (nodeId: string) => {
      if (!navStart || (navStart && navEnd)) {
        setNavStart(nodeId);
        setNavEnd(null);
        setError(null);
        return;
      }
      if (nodeId === navStart) {
        setError("终点不能与起点相同");
        return;
      }
      setNavEnd(nodeId);
      setBusy(true);
      setError(null);
      try {
        const res = await postRoutePlan({
          start_node: navStart,
          end_node: nodeId,
          duration_s: draft.duration_s,
          clear_obstacles: true,
        });
        setDraft(res.draft);
        setSelectedLinkIdx(0);
        setSelectedObstacleIdx(null);
      } catch (e) {
        setError(String((e as Error).message || e));
        setNavEnd(null);
      } finally {
        setBusy(false);
      }
    },
    [navStart, navEnd, draft.duration_s]
  );

  const paused = status.status === "paused";

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">AutoSim</span>
          <span className="brand-sub">网页实时鸟瞰 · 自定义路线</span>
        </div>
        <div className="transport">
          <button
            type="button"
            className="btn primary"
            disabled={busy || status.status === "running"}
            onClick={() => runControl("start")}
          >
            开始
          </button>
          <button
            type="button"
            className="btn"
            disabled={busy || status.status !== "running"}
            onClick={() => runControl("pause")}
          >
            暂停
          </button>
          <button
            type="button"
            className="btn"
            disabled={busy || status.status !== "paused"}
            onClick={() => runControl("resume")}
          >
            继续
          </button>
          <button
            type="button"
            className="btn"
            disabled={busy}
            onClick={() => runControl("reset")}
          >
            重置
          </button>
        </div>
        <div className="meta">
          <span className={wsOk ? "dot on" : "dot"} />
          <span>
            {statusZh(status.status)} · t={status.t.toFixed(2)}/{status.duration_s.toFixed(0)}s
          </span>
          <span className="hint-key">空格键 = 开始/暂停</span>
        </div>
      </header>

      <main className="main">
        <section className="stage">
          <BirdEyeCanvas
            snapshot={snapshot}
            paused={paused}
            draft={draft}
            editTool={editTool}
            selectedLinkIdx={selectedLinkIdx}
            selectedObstacleIdx={selectedObstacleIdx}
            onChangeDraft={setDraft}
            onSelectLink={setSelectedLinkIdx}
            onSelectObstacle={setSelectedObstacleIdx}
            baseMap={baseMap}
            navStart={navStart}
            navEnd={navEnd}
            onNavPick={onNavPick}
          />
        </section>
        <ConfigPanel
          draft={draft}
          onChange={setDraft}
          onApply={onApply}
          presets={presets}
          onLoadPreset={onLoadPreset}
          busy={busy}
          error={error}
          editTool={editTool}
          onEditTool={setEditTool}
          selectedLinkIdx={selectedLinkIdx}
          onSelectLink={setSelectedLinkIdx}
          selectedObstacleIdx={selectedObstacleIdx}
          onSelectObstacle={setSelectedObstacleIdx}
        />
      </main>
    </div>
  );
}
