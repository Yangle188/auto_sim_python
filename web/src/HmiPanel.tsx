import { adStateZh } from "./labels";
import type { HmiAlert, HmiPayload } from "./types";

interface Props {
  adState: string;
  hmi?: HmiPayload | null;
  engagePending?: boolean;
}

function levelClass(level: string): string {
  const l = (level || "INFO").toUpperCase();
  if (l === "FAULT") return "fault";
  if (l === "ALERT") return "alert";
  if (l === "WARNING") return "warning";
  return "info";
}

function codeLabel(code: string): string {
  switch (code) {
    case "ad_activate":
      return "激活";
    case "ad_exit":
      return "退出";
    case "speed_limit":
      return "限速";
    default:
      return "状态";
  }
}

export function HmiPanel({ adState, hmi, engagePending }: Props) {
  const state = hmi?.ad_state || adState || "OFF";
  const alerts: HmiAlert[] = hmi?.alerts || [];
  const latest = hmi?.latest || alerts[0] || null;
  const stateMod = state.toLowerCase();

  return (
    <aside className={`hmi-panel state-${stateMod}`} aria-label="HMI 人机界面">
      <div className="hmi-head">
        <span className="hmi-title">HMI</span>
        <span className={`hmi-state-badge state-${stateMod}`}>
          {adStateZh(state)}
        </span>
      </div>
      <div className="hmi-state-row">
        <span className="hmi-state-label">功能状态</span>
        <strong className={`hmi-state-value state-${stateMod}`}>
          {adStateZh(state)}
          {engagePending && state === "STANDBY" ? " · 待激活" : ""}
        </strong>
      </div>
      {latest ? (
        <div
          className={`hmi-toast level-${levelClass(latest.level)} code-${latest.code || "other"}`}
          role="status"
        >
          <span className="hmi-toast-tag">{codeLabel(latest.code || "")}</span>
          <span className="hmi-toast-msg">{latest.msg}</span>
          {typeof latest.t === "number" ? (
            <span className="hmi-toast-t">t={latest.t.toFixed(1)}s</span>
          ) : null}
        </div>
      ) : (
        <div className="hmi-toast empty">暂无提示</div>
      )}
      <ul className="hmi-log">
        {alerts.slice(0, 8).map((a, i) => (
          <li key={`${a.code}-${a.msg}-${a.t ?? i}-${i}`} className={`level-${levelClass(a.level)}`}>
            <span className="hmi-log-tag">{codeLabel(a.code || "")}</span>
            <span className="hmi-log-msg">{a.msg}</span>
          </li>
        ))}
      </ul>
    </aside>
  );
}
