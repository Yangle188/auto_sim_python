import { adStateZh } from "../labels";
import type { ChannelMetrics } from "../data/selectors";

interface Props {
  metrics: ChannelMetrics;
  visible?: boolean;
}

function AdasIcon({
  label,
  active,
  warn,
  alert,
  title,
}: {
  label: string;
  active?: boolean;
  warn?: boolean;
  alert?: boolean;
  title: string;
}) {
  const mod = alert ? " alert" : warn ? " warn" : active ? " on" : "";
  return (
    <span className={`adas-icon${mod}`} title={title}>
      {label}
    </span>
  );
}

/**
 * 驾驶席仪表 PIP：速度弧 + AD 灯 + ADAS 图标 + 脱手条。
 * 数据来自节流 uiFrame（不驱动 BirdEyeViewport re-render）。
 */
export function InstrumentCluster({ metrics, visible = true }: Props) {
  if (!visible) return null;

  const speedKmh = metrics.speed * 3.6;
  const limit = metrics.speedLimit;
  const vCmd = metrics.vCmd;
  const refSpeed = limit ?? vCmd ?? 20;
  const arcMax = Math.max(40, refSpeed * 1.25, metrics.speed + 5);
  const frac = Math.max(0, Math.min(1, metrics.speed / arcMax));
  const limitFrac =
    limit != null ? Math.max(0, Math.min(1, limit / arcMax)) : null;

  // 半圆弧：从 210° 到 -30°（CSS 坐标系）
  const start = (-210 * Math.PI) / 180;
  const sweep = ((210 + 30) * Math.PI) / 180;
  const r = 54;
  const cx = 70;
  const cy = 68;
  const polar = (t: number) => {
    const a = start + sweep * t;
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  };
  const [x0, y0] = polar(0);
  const [x1, y1] = polar(frac);
  const large = frac > 0.5 ? 1 : 0;
  const speedArc = `M ${x0} ${y0} A ${r} ${r} 0 ${large} 1 ${x1} ${y1}`;

  let limitArc: string | null = null;
  if (limitFrac != null) {
    const [lx, ly] = polar(limitFrac);
    limitArc = `M ${x0} ${y0} A ${r} ${r} 0 ${limitFrac > 0.5 ? 1 : 0} 1 ${lx} ${ly}`;
  }

  const ad = (metrics.adState || "OFF").toLowerCase();
  const aebOn = metrics.aebMode === "aeb";
  const fcwOn = metrics.aebMode === "fcw";
  const handsFrac =
    metrics.handsOffS != null
      ? Math.min(1, metrics.handsOffS / Math.max(0.1, metrics.handsOffTorS))
      : 0;
  const handsMod =
    metrics.handsOffS == null
      ? ""
      : metrics.handsOffS >= metrics.handsOffTorS
        ? " danger"
        : metrics.handsOffS >= metrics.handsOffWarnS
          ? " warn"
          : "";

  return (
    <div className="instrument-cluster" aria-label="仪表簇">
      <svg className="cluster-gauge" viewBox="0 0 140 100" aria-hidden>
        <path
          d={`M ${polar(0)[0]} ${polar(0)[1]} A ${r} ${r} 0 1 1 ${polar(1)[0]} ${polar(1)[1]}`}
          className="gauge-track"
        />
        {limitArc ? <path d={limitArc} className="gauge-limit" /> : null}
        <path d={speedArc} className="gauge-speed" />
      </svg>
      <div className="cluster-speed">
        <span className="cluster-speed-num">{speedKmh.toFixed(0)}</span>
        <span className="cluster-speed-unit">km/h</span>
      </div>
      <div className="cluster-meta">
        {limit != null ? (
          <span title="限速">限 {limit.toFixed(0)} m/s</span>
        ) : (
          <span>无限速</span>
        )}
        {vCmd != null ? (
          <span title="纵向指令">v* {vCmd.toFixed(1)}</span>
        ) : null}
      </div>

      <div className={`cluster-ad ad-${ad}`}>
        <span className="ad-dot" />
        <span>{adStateZh(metrics.adState || "OFF")}</span>
      </div>

      <div className="adas-row">
        <AdasIcon
          label="LCC"
          active={metrics.adState === "ACTIVE" || metrics.adState === "STANDBY"}
          title="车道居中"
        />
        <AdasIcon label="ACC" active={metrics.accActive} title="自适应巡航跟车" />
        <AdasIcon label="FCW" warn={fcwOn} title="前方碰撞预警" />
        <AdasIcon label="AEB" alert={aebOn} title="自动紧急制动" />
        <AdasIcon label="Nudge" active={metrics.nudgeActive} title="同车道绕障" />
        <AdasIcon
          label="LC"
          active={metrics.lcActive}
          title="拨杆变道进行中"
        />
        <AdasIcon
          label="Hands"
          warn={metrics.handsOffWarned && !metrics.torPending}
          alert={metrics.torPending}
          active={metrics.handsOffTracking && !metrics.handsOffWarned}
          title="脱手监测"
        />
      </div>

      <div className="cluster-secs">
        <span title="横向误差">
          e⊥ {metrics.latErrM == null ? "—" : `${metrics.latErrM.toFixed(2)} m`}
        </span>
        <span title="跟车间隙">
          d {metrics.dGap == null ? "—" : `${metrics.dGap.toFixed(1)} m`}
        </span>
        <span title="碰撞时间">
          TTC {metrics.ttc == null ? "—" : `${metrics.ttc.toFixed(1)} s`}
        </span>
      </div>

      {metrics.handsOffTracking ? (
        <div
          className={`cluster-hands${handsMod}`}
          title={`脱手 ${metrics.handsOffS?.toFixed(1)}s / 告警 ${metrics.handsOffWarnS}s / TOR ${metrics.handsOffTorS}s`}
        >
          <span className="cluster-hands-label">
            脱手 {(metrics.handsOffS ?? 0).toFixed(0)}s
          </span>
          <span className="hands-off-bar">
            <span style={{ width: `${(handsFrac * 100).toFixed(1)}%` }} />
          </span>
        </div>
      ) : null}
    </div>
  );
}
