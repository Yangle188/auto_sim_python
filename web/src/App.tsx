import { useCallback, useEffect, useState } from "react";
import { BirdEyeCanvas } from "./BirdEyeCanvas";
import { ConfigPanel } from "./ConfigPanel";
import { HmiPanel } from "./HmiPanel";
import { Timeline } from "./Timeline";
import {
  fetchBasemap,
  fetchPresets,
  fetchScene,
  postControl,
  postRoutePlan,
  putScene,
  simWsUrl,
  type ControlAction,
} from "./api";
import { adStateZh, statusZh } from "./labels";
import type { EditTool } from "./sceneEdit";
import type {
  BaseMapData,
  PresetMeta,
  SceneConfig,
  Snapshot,
  StatusPayload,
} from "./types";

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
  const [keepObstaclesOnNav, setKeepObstaclesOnNav] = useState(false);

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

  const runControl = useCallback(
    async (
      action: ControlAction,
      extra?: { frame_i?: number; direction?: "left" | "right" }
    ) => {
      setBusy(true);
      setError(null);
      try {
        if (action === "start" || action === "reset") {
          await putScene(draft);
          if (action === "start") {
            await postControl("reset");
          }
        }
        const res = await postControl(action === "start" ? "start" : action, extra);
        setStatus(res.status);
        if (res.frame) setSnapshot(res.frame as Snapshot);
        if (action === "reset" || action === "start") {
          if (action === "reset") setSnapshot(null);
          if (action === "start") setEditTool("none");
        }
      } catch (e) {
        setError(String((e as Error).message || e));
      } finally {
        setBusy(false);
      }
    },
    [draft]
  );

  const onSeek = useCallback(
    (frameI: number) => {
      void runControl("seek", { frame_i: frameI });
    },
    [runControl]
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      if (e.code === "Space") {
        e.preventDefault();
        if (status.status === "running") runControl("pause");
        else if (status.status === "paused") runControl("resume");
        else runControl("start");
        return;
      }
      if (e.code === "ArrowLeft") {
        e.preventDefault();
        runControl("step_prev");
        return;
      }
      if (e.code === "ArrowRight") {
        e.preventDefault();
        runControl("step_next");
        return;
      }
      if (e.key === "[" || e.code === "BracketLeft") {
        e.preventDefault();
        runControl("lane_change", { direction: "left" });
        return;
      }
      if (e.key === "]" || e.code === "BracketRight") {
        e.preventDefault();
        runControl("lane_change", { direction: "right" });
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
      const res = await postControl("start");
      setStatus(res.status);
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
          clear_obstacles: !keepObstaclesOnNav,
        });
        setDraft(res.draft);
        setSelectedLinkIdx(0);
        setSelectedObstacleIdx(res.draft.obstacles.length ? 0 : null);
      } catch (e) {
        setError(String((e as Error).message || e));
        setNavEnd(null);
      } finally {
        setBusy(false);
      }
    },
    [navStart, navEnd, draft.duration_s, keepObstaclesOnNav]
  );

  const paused = status.status === "paused";
  const frameI = status.frame_i ?? -1;
  const frameN = status.frame_n ?? 0;
  const frameTotal = status.frame_total ?? frameN;
  const canStep = !busy && editTool === "none";
  const adState = status.ad_state ?? snapshot?.state ?? "";
  const canActivate =
    status.can_activate ??
    (adState === "STANDBY" &&
      (status.status === "running" || status.status === "paused"));
  const canDeactivate =
    status.can_deactivate ??
    (adState === "ACTIVE" &&
      (status.status === "running" || status.status === "paused"));
  const activateDisabled =
    busy ||
    !canActivate ||
    status.status === "idle" ||
    status.status === "finished";
  const deactivateDisabled =
    busy ||
    !canDeactivate ||
    status.status === "idle" ||
    status.status === "finished";
  const canLaneChange =
    (status.can_lane_change ?? false) &&
    (status.status === "running" || status.status === "paused");
  const laneChangeDisabled =
    busy || !canLaneChange || status.status === "idle" || status.status === "finished";
  const activateTitle = status.ad_engage_pending
    ? "已请求激活，等待车速进入允许区间（约 5–30 m/s）"
    : activateDisabled
      ? status.status === "idle"
        ? "请先点「开始」"
        : adState && adState !== "STANDBY"
          ? `当前 AD 为「${adStateZh(adState)}」，需进入待机(STANDBY)后才能激活（约 t≥2.5s）`
          : "当前不可激活"
      : "STANDBY → ACTIVE（车速未就绪时会挂起，达速后自动切入）";

  const laneIdx =
    status.lane_change?.lane_index ?? snapshot?.lane_index ?? null;
  const aebMode = snapshot?.aeb?.mode;

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
            disabled={!canStep || frameN <= 0 || frameI <= 0}
            onClick={() => runControl("step_prev")}
            title="上一帧（←）"
          >
            上一帧
          </button>
          <button
            type="button"
            className="btn"
            disabled={!canStep || status.status === "running"}
            onClick={() => runControl("step_next")}
            title="下一帧（→）；在最新帧时单步推进"
          >
            下一帧
          </button>
          <button
            type="button"
            className="btn accent"
            disabled={activateDisabled}
            onClick={() => runControl("activate")}
            title={activateTitle}
          >
            {status.ad_engage_pending ? "激活中…" : "激活"}
          </button>
          <button
            type="button"
            className="btn"
            disabled={deactivateDisabled}
            onClick={() => runControl("deactivate")}
            title="ACTIVE → STANDBY，功能退出"
          >
            退出
          </button>
          <button
            type="button"
            className="btn accent"
            disabled={laneChangeDisabled}
            onClick={() => runControl("lane_change", { direction: "left" })}
            title="拨杆左变道（[）"
          >
            左变道
          </button>
          <button
            type="button"
            className="btn accent"
            disabled={laneChangeDisabled}
            onClick={() => runControl("lane_change", { direction: "right" })}
            title="拨杆右变道（]）"
          >
            右变道
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
            {statusZh(status.status)}
            {adState ? ` · AD ${adStateZh(adState)}` : ""}
            {laneIdx != null ? ` · 车道${laneIdx}` : ""}
            {status.lane_change?.state && status.lane_change.state !== "idle"
              ? ` · 变道:${status.lane_change.state}`
              : ""}
            {aebMode && aebMode !== "none" ? ` · ${String(aebMode).toUpperCase()}` : ""}
            {status.ad_engage_pending ? " · 待激活" : ""}
            {status.scrubbing ? " · 回看" : ""} · t={status.t.toFixed(2)}/
            {status.duration_s.toFixed(0)}s
            {frameN > 0 ? ` · 帧 ${Math.max(0, frameI) + 1}/${frameN}` : ""}
          </span>
          <span className="hint-key">
            空格=开始/暂停 · ←/→=逐帧 · [/]=拨杆变道 · 达速后点「激活」
          </span>
        </div>
      </header>

      <Timeline
        frameI={frameI}
        frameN={frameN}
        frameTotal={frameTotal}
        t={status.t}
        durationS={status.duration_s}
        scrubbing={!!status.scrubbing}
        disabled={!canStep}
        onSeek={onSeek}
      />

      <main className="main">
        <section className="stage">
          <div className="stage-with-hmi">
            <BirdEyeCanvas
              snapshot={snapshot}
              paused={paused || !!status.scrubbing}
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
            <HmiPanel
              adState={adState}
              hmi={snapshot?.hmi}
              engagePending={!!status.ad_engage_pending}
            />
          </div>
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
          keepObstaclesOnNav={keepObstaclesOnNav}
          onKeepObstaclesOnNav={setKeepObstaclesOnNav}
        />
      </main>
    </div>
  );
}
