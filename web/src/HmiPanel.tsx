import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
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

/** 事件日志 code → 短标签（与后端 hmi CODE_* 对齐） */
function codeLabel(code: string): string {
  switch (code) {
    case "ad_activate":
      return "激活";
    case "ad_exit":
      return "退出";
    case "engage":
      return "请求";
    case "speed_limit":
      return "限速";
    case "lane_change_start":
      return "变道";
    case "lane_change_done":
      return "变道";
    case "lane_change_abort":
      return "变道";
    case "lane_change_reject":
      return "变道";
    case "fcw":
      return "FCW";
    case "aeb":
      return "AEB";
    case "aeb_clear":
      return "AEB";
    case "acc":
      return "ACC";
    case "scene":
      return "场景";
    case "lcc":
      return "LCC";
    case "state_change":
      return "状态";
    case "tor":
      return "TOR";
    case "override":
      return "接管";
    case "auto_maneuver":
      return "机动";
    case "nudge":
      return "绕障";
    case "hands_off":
      return "脱手";
    case "teach":
      return "教学";
    default:
      return "事件";
  }
}

const PAD = 12;

export function HmiPanel({ adState, hmi, engagePending }: Props) {
  const state = hmi?.ad_state || adState || "OFF";
  const alerts: HmiAlert[] = hmi?.alerts || [];
  const latest = hmi?.latest || alerts[0] || null;
  const stateMod = state.toLowerCase();

  const panelRef = useRef<HTMLElement>(null);
  const dragRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    origLeft: number;
    origTop: number;
  } | null>(null);
  const [pos, setPos] = useState({ left: PAD, top: PAD });
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    const clamp = () => {
      const el = panelRef.current;
      const parent = el?.offsetParent as HTMLElement | null;
      if (!el || !parent) return;
      const maxL = Math.max(PAD, parent.clientWidth - el.offsetWidth - PAD);
      const maxT = Math.max(PAD, parent.clientHeight - el.offsetHeight - PAD);
      setPos((p) => ({
        left: Math.min(Math.max(PAD, p.left), maxL),
        top: Math.min(Math.max(PAD, p.top), maxT),
      }));
    };
    clamp();
    window.addEventListener("resize", clamp);
    return () => window.removeEventListener("resize", clamp);
  }, [alerts.length, latest?.msg]);

  const onDragStart = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    e.preventDefault();
    e.currentTarget.setPointerCapture(e.pointerId);
    dragRef.current = {
      pointerId: e.pointerId,
      startX: e.clientX,
      startY: e.clientY,
      origLeft: pos.left,
      origTop: pos.top,
    };
    setDragging(true);
  };

  const onDragMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    const d = dragRef.current;
    if (!d || d.pointerId !== e.pointerId) return;
    const el = panelRef.current;
    const parent = el?.offsetParent as HTMLElement | null;
    if (!el || !parent) return;
    const maxL = Math.max(PAD, parent.clientWidth - el.offsetWidth - PAD);
    const maxT = Math.max(PAD, parent.clientHeight - el.offsetHeight - PAD);
    const nextL = d.origLeft + (e.clientX - d.startX);
    const nextT = d.origTop + (e.clientY - d.startY);
    setPos({
      left: Math.min(Math.max(PAD, nextL), maxL),
      top: Math.min(Math.max(PAD, nextT), maxT),
    });
  };

  const onDragEnd = (e: ReactPointerEvent<HTMLDivElement>) => {
    const d = dragRef.current;
    if (!d || d.pointerId !== e.pointerId) return;
    dragRef.current = null;
    setDragging(false);
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      /* already released */
    }
  };

  return (
    <aside
      ref={panelRef}
      className={`hmi-panel state-${stateMod}${dragging ? " dragging" : ""}`}
      aria-label="HMI 人机界面"
      style={{ left: pos.left, top: pos.top }}
    >
      <div
        className="hmi-head"
        onPointerDown={onDragStart}
        onPointerMove={onDragMove}
        onPointerUp={onDragEnd}
        onPointerCancel={onDragEnd}
        title="拖动移动窗口"
      >
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
      <div className="hmi-log-head">事件日志</div>
      <ul className="hmi-log">
        {alerts.length === 0 ? (
          <li className="hmi-log-empty">开始仿真后显示场景与功能事件</li>
        ) : (
          alerts.slice(0, 24).map((a, i) => (
            <li
              key={`${a.code}-${a.msg}-${a.t ?? i}-${i}`}
              className={`level-${levelClass(a.level)}`}
            >
              <span className="hmi-log-meta">
                <span className="hmi-log-tag">{codeLabel(a.code || "")}</span>
                {typeof a.t === "number" ? (
                  <span className="hmi-log-t">{a.t.toFixed(1)}s</span>
                ) : null}
              </span>
              <span className="hmi-log-msg">{a.msg}</span>
            </li>
          ))
        )}
      </ul>
    </aside>
  );
}
