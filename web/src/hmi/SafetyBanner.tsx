import type { HmiAlert, Snapshot, StatusPayload } from "../types";

interface Props {
  status: StatusPayload;
  /** 节流后的展示帧（非每仿真帧） */
  uiFrame: Snapshot | null;
}

type BannerLevel = "info" | "warn" | "alert" | null;

function pickBanner(
  status: StatusPayload,
  uiFrame: Snapshot | null
): { level: BannerLevel; text: string } | null {
  const aeb = uiFrame?.aeb?.mode;
  const tor = status.tor_pending || uiFrame?.tor_pending;
  const latest: HmiAlert | null | undefined = uiFrame?.hmi?.latest;
  const dms = status.dms;

  if (aeb === "aeb" || tor) {
    return {
      level: "alert",
      text: tor
        ? "TOR · 请立即接管车辆"
        : `AEB · 自动紧急制动${
            uiFrame?.aeb?.d_gap != null ? ` · d=${uiFrame.aeb.d_gap.toFixed(1)}m` : ""
          }`,
    };
  }
  if (aeb === "fcw" || (dms?.warned && !dms?.tor_requested)) {
    return {
      level: "warn",
      text:
        aeb === "fcw"
          ? `FCW · 请注意前方${
              uiFrame?.aeb?.ttc != null ? ` · TTC=${uiFrame.aeb.ttc.toFixed(1)}s` : ""
            }`
          : `脱手告警 · ${(dms?.hands_off_s ?? 0).toFixed(0)}s`,
    };
  }
  if (latest && (latest.level || "").toUpperCase() === "WARNING") {
    return { level: "warn", text: latest.msg };
  }
  if (latest && (latest.level || "").toUpperCase() === "INFO") {
    return { level: "info", text: latest.msg };
  }
  return null;
}

/** 全宽安全横幅：只显示当前最高优先级 */
export function SafetyBanner({ status, uiFrame }: Props) {
  const ban = pickBanner(status, uiFrame);
  if (!ban || !ban.level) return null;
  return (
    <div className={`safety-banner ${ban.level}`} role="status">
      {ban.text}
    </div>
  );
}
