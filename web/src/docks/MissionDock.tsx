import type { ControlAction } from "../api";
import { adStateZh } from "../labels";
import type { StatusPayload } from "../types";

interface Props {
  status: StatusPayload;
  busy: boolean;
  useTruthLeads: boolean;
  useEstPose: boolean;
  onControl: (
    action: ControlAction,
    extra?: {
      direction?: "left" | "right";
      use_truth_leads?: boolean;
      use_est_pose_lateral?: boolean;
    }
  ) => void;
}

export function MissionDock({
  status,
  busy,
  useTruthLeads,
  useEstPose,
  onControl,
}: Props) {
  const adState = status.ad_state ?? "";
  const running =
    status.status === "running" || status.status === "paused";
  const idleOrDone =
    status.status === "idle" || status.status === "finished";

  const activateDisabled =
    busy || !(status.can_activate ?? false) || idleOrDone;
  const deactivateDisabled =
    busy || !(status.can_deactivate ?? false) || idleOrDone;
  const laneChangeDisabled =
    busy || !(status.can_lane_change ?? false) || idleOrDone;
  const torDisabled = busy || !(status.can_tor ?? false) || idleOrDone;
  const overrideDisabled =
    busy || !(status.can_override ?? false) || idleOrDone;
  const handsOnDisabled =
    busy ||
    !(status.can_hands_on ?? adState === "ACTIVE") ||
    idleOrDone;

  return (
    <div className="mission-dock">
      <div className="mission-card">
        <div className="mission-label">自动驾驶</div>
        <div className={`mission-ad ad-${(adState || "off").toLowerCase()}`}>
          {adState ? adStateZh(adState) : "—"}
        </div>
        {status.ad_engage_pending ? (
          <div className="mission-hint">待激活 · 等待车速就绪</div>
        ) : null}
        {status.lane_change?.state && status.lane_change.state !== "idle" ? (
          <div className="mission-hint">
            变道 {status.lane_change.state}
            {status.lane_change.direction
              ? ` · ${status.lane_change.direction}`
              : ""}
          </div>
        ) : null}
        {status.nudge?.state === "nudging" ? (
          <div className="mission-hint">
            绕障 {status.nudge.side === "right" ? "右" : "左"}
          </div>
        ) : null}
      </div>

      <div className="mission-actions">
        <button
          type="button"
          className="btn accent"
          disabled={activateDisabled}
          onClick={() => onControl("activate")}
        >
          {status.ad_engage_pending ? "激活中…" : "激活"}
        </button>
        <button
          type="button"
          className="btn"
          disabled={deactivateDisabled}
          onClick={() => onControl("deactivate")}
        >
          退出
        </button>
        <button
          type="button"
          className="btn accent"
          disabled={laneChangeDisabled}
          onClick={() => onControl("lane_change", { direction: "left" })}
          title="["
        >
          左变道
        </button>
        <button
          type="button"
          className="btn accent"
          disabled={laneChangeDisabled}
          onClick={() => onControl("lane_change", { direction: "right" })}
          title="]"
        >
          右变道
        </button>
        <button
          type="button"
          className={`btn${status.tor_pending ? " accent" : ""}`}
          disabled={torDisabled}
          onClick={() => onControl("tor")}
        >
          {status.tor_pending ? "TOR 中…" : "请求接管"}
        </button>
        <button
          type="button"
          className="btn accent"
          disabled={overrideDisabled}
          onClick={() => onControl("override")}
          title="O"
        >
          接管
        </button>
        <button
          type="button"
          className="btn"
          disabled={handsOnDisabled}
          onClick={() => onControl("hands_on")}
          title="H"
        >
          双手在环
        </button>
      </div>

      <details className="mission-teach" open={false}>
        <summary>教学开关</summary>
        <div className="mission-actions">
          <button
            type="button"
            className={`btn${useTruthLeads ? "" : " accent"}`}
            disabled={busy || !running}
            onClick={() =>
              onControl("set_teaching", { use_truth_leads: !useTruthLeads })
            }
          >
            {useTruthLeads ? "Leads·真值" : "Leads·感知"}
          </button>
          <button
            type="button"
            className={`btn${useEstPose ? " accent" : ""}`}
            disabled={busy || !running}
            onClick={() =>
              onControl("set_teaching", {
                use_est_pose_lateral: !useEstPose,
              })
            }
          >
            {useEstPose ? "横向·估计" : "横向·真值"}
          </button>
        </div>
      </details>
    </div>
  );
}
