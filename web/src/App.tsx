import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BirdEyeViewport } from "./viewports/BirdEyeViewport";
import { ConfigPanel } from "./ConfigPanel";
import { HmiPanel } from "./HmiPanel";
import { Timeline } from "./Timeline";
import { InstrumentCluster } from "./cluster/InstrumentCluster";
import { selectChannelMetrics } from "./data/selectors";
import { MissionDock } from "./docks/MissionDock";
import { SafetyBanner } from "./hmi/SafetyBanner";
import { ChannelStrip } from "./layout/ChannelStrip";
import { SideDock, type DockTab } from "./layout/SideDock";
import { ViewportHost } from "./layout/ViewportHost";
import { MODE_LABEL, deriveMode, type UiMode } from "./app/modeMachine";
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

const UI_FRAME_MS = 200;

export default function App() {
  /** 仿真帧：仅写 ref，供 BirdEyeViewport rAF 读取 */
  const frameRef = useRef<Snapshot | null>(null);
  const lastUiFrameAt = useRef(0);
  /** 节流展示帧：HMI / Banner / meta，非每仿真帧 */
  const [uiFrame, setUiFrame] = useState<Snapshot | null>(null);
  const [status, setStatus] = useState<StatusPayload>({
    status: "idle",
    t: 0,
    duration_s: 35,
  });
  const [draft, setDraft] = useState<SceneConfig>(EMPTY);
  const [applied, setApplied] = useState<SceneConfig | null>(null);
  const [presets, setPresets] = useState<PresetMeta[]>([]);
  const [scenes, setScenes] = useState<Record<string, SceneConfig>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [wsOk, setWsOk] = useState(false);
  const [editTool, setEditTool] = useState<EditTool>("none");
  const [selectedLinkIdx, setSelectedLinkIdx] = useState(0);
  const [selectedObstacleIdx, setSelectedObstacleIdx] = useState<number | null>(
    null
  );
  const [baseMap, setBaseMap] = useState<BaseMapData | null>(null);
  const [navStart, setNavStart] = useState<string | null>(null);
  const [navEnd, setNavEnd] = useState<string | null>(null);
  const [keepObstaclesOnNav, setKeepObstaclesOnNav] = useState(false);
  const [userMode, setUserMode] = useState<UiMode | null>(null);
  const [dockTab, setDockTab] = useState<DockTab>("mission");
  const [dockHover, setDockHover] = useState(false);
  const [channelCollapsed, setChannelCollapsed] = useState(false);

  useEffect(() => {
    Promise.all([fetchScene(), fetchPresets(), fetchBasemap()])
      .then(([sceneData, presetData, bm]) => {
        setDraft(sceneData.draft);
        setApplied(sceneData.applied);
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
          if (msg.type === "frame") {
            const snap = msg.data as Snapshot;
            frameRef.current = snap;
            const now = performance.now();
            if (now - lastUiFrameAt.current >= UI_FRAME_MS) {
              lastUiFrameAt.current = now;
              setUiFrame(snap);
            }
          }
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
      extra?: {
        frame_i?: number;
        direction?: "left" | "right";
        use_truth_leads?: boolean;
        use_est_pose_lateral?: boolean;
      }
    ) => {
      setBusy(true);
      setError(null);
      try {
        if (action === "start" || action === "reset") {
          await putScene(draft);
          setApplied(JSON.parse(JSON.stringify(draft)) as SceneConfig);
          if (action === "start") {
            await postControl("reset");
          }
        }
        const res = await postControl(action === "start" ? "start" : action, extra);
        setStatus(res.status);
        if (res.frame) {
          const snap = res.frame as Snapshot;
          frameRef.current = snap;
          setUiFrame(snap);
        }
        if (action === "reset" || action === "start") {
          if (action === "reset") {
            frameRef.current = null;
            setUiFrame(null);
          }
          if (action === "start") {
            setEditTool("none");
            setUserMode("drive");
            setDockTab("mission");
          }
        }
        if (action === "set_teaching") {
          setDraft((d) => ({
            ...d,
            use_truth_leads:
              extra?.use_truth_leads ?? d.use_truth_leads ?? true,
            use_est_pose_lateral:
              extra?.use_est_pose_lateral ?? d.use_est_pose_lateral ?? false,
          }));
          setApplied((a) =>
            a
              ? {
                  ...a,
                  use_truth_leads:
                    extra?.use_truth_leads ?? a.use_truth_leads ?? true,
                  use_est_pose_lateral:
                    extra?.use_est_pose_lateral ??
                    a.use_est_pose_lateral ??
                    false,
                }
              : a
          );
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
        return;
      }
      if (e.key === "o" || e.key === "O") {
        e.preventDefault();
        runControl("override");
        return;
      }
      if (e.key === "h" || e.key === "H") {
        e.preventDefault();
        runControl("hands_on");
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
      setApplied(JSON.parse(JSON.stringify(draft)) as SceneConfig);
      await postControl("reset");
      const res = await postControl("start");
      setStatus(res.status);
      frameRef.current = null;
      setUiFrame(null);
      setEditTool("none");
      setUserMode("drive");
      setDockTab("mission");
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
      setUserMode("author");
      setDockTab("scene");
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
  const adState = status.ad_state ?? uiFrame?.state ?? "";
  const draftDirty =
    applied != null && JSON.stringify(draft) !== JSON.stringify(applied);
  const useTruthLeads =
    status.use_truth_leads ??
    uiFrame?.use_truth_leads ??
    draft.use_truth_leads ??
    true;
  const useEstPose =
    status.use_est_pose_lateral ??
    uiFrame?.use_est_pose_lateral ??
    draft.use_est_pose_lateral ??
    false;

  const mode = useMemo(
    () => deriveMode(status, userMode, editTool !== "none"),
    [status, userMode, editTool]
  );

  const metrics = useMemo(
    () => selectChannelMetrics(uiFrame, status),
    [uiFrame, status]
  );

  useEffect(() => {
    if (editTool !== "none") {
      setDockTab("scene");
      setUserMode("author");
    }
  }, [editTool]);

  // Review 默认展开通道；Author 折叠以腾编辑空间
  useEffect(() => {
    if (mode === "author") setChannelCollapsed(true);
    else if (mode === "review") setChannelCollapsed(false);
  }, [mode]);

  return (
    <div className={`app mode-${mode}`}>
      <header className="topbar shell-header">
        <div className="brand">
          <span className="brand-mark">AutoSim</span>
          <span className="brand-sub">仿真台 · P-UI1</span>
        </div>
        <div className="mode-tabs" role="tablist" aria-label="工作模式">
          {(["author", "drive", "review"] as UiMode[]).map((m) => (
            <button
              key={m}
              type="button"
              role="tab"
              className={`mode-tab${mode === m ? " active" : ""}`}
              aria-selected={mode === m}
              onClick={() => {
                setUserMode(m);
                if (m === "author") setDockTab("scene");
                if (m === "drive") {
                  setEditTool("none");
                  setDockTab("mission");
                }
                if (m === "review") setDockTab("events");
              }}
            >
              {MODE_LABEL[m]}
            </button>
          ))}
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
            title="下一帧（→）"
          >
            下一帧
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
            {MODE_LABEL[mode]} · {statusZh(status.status)}
            {adState ? ` · AD ${adStateZh(adState)}` : ""}
            {draftDirty ? " · 草稿未应用" : ""}
            {status.scrubbing ? " · 回看" : ""} · t={status.t.toFixed(2)}/
            {status.duration_s.toFixed(0)}s
            {frameN > 0 ? ` · 帧 ${Math.max(0, frameI) + 1}/${frameN}` : ""}
          </span>
          <span className="hint-key">
            空格=开始/暂停 · ←/→=逐帧 · [/]=变道 · Mission 栏驾驶操作
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

      <SafetyBanner status={status} uiFrame={uiFrame} />

      <main className="main">
        <ViewportHost
          canvasInteractive={!dockHover}
          pip={
            <InstrumentCluster
              metrics={metrics}
              visible={mode !== "author" || status.status !== "idle"}
            />
          }
          overlay={
            dockTab === "events" ? null : (
              <HmiPanel
                adState={adState}
                hmi={uiFrame?.hmi}
                engagePending={!!status.ad_engage_pending}
              />
            )
          }
        >
          <BirdEyeViewport
            frameRef={frameRef}
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
            pointerEvents={!dockHover ? "auto" : "none"}
          />
        </ViewportHost>

        <SideDock
          tab={dockTab}
          onTab={setDockTab}
          onHoverChange={setDockHover}
          mission={
            <MissionDock
              status={status}
              busy={busy}
              useTruthLeads={useTruthLeads}
              useEstPose={useEstPose}
              onControl={runControl}
            />
          }
          scene={
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
              dirty={draftDirty}
            />
          }
          events={
            <div className="events-dock">
              <HmiPanel
                adState={adState}
                hmi={uiFrame?.hmi}
                engagePending={!!status.ad_engage_pending}
              />
            </div>
          }
        />
      </main>

      <ChannelStrip
        metrics={metrics}
        collapsed={channelCollapsed}
        onToggle={() => setChannelCollapsed((c) => !c)}
      />
    </div>
  );
}
