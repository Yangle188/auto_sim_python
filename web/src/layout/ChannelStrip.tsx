import type { ChannelMetrics } from "../data/selectors";

interface Props {
  metrics: ChannelMetrics;
  collapsed?: boolean;
  onToggle?: () => void;
}

interface Cell {
  key: string;
  label: string;
  value: string;
  unit?: string;
  bar?: number; // 0..1
  tone?: "warn" | "danger" | "ok";
}

function cellsOf(m: ChannelMetrics): Cell[] {
  const steerAbs = m.steer == null ? null : Math.min(1, Math.abs(m.steer));
  const accelBar =
    m.accel == null ? null : Math.min(1, Math.abs(m.accel) / 3);
  const handsBar =
    m.handsOffS == null
      ? null
      : Math.min(1, m.handsOffS / Math.max(0.1, m.handsOffTorS));

  return [
    {
      key: "speed",
      label: "speed",
      value: m.speed.toFixed(1),
      unit: "m/s",
      bar: Math.min(1, m.speed / 25),
    },
    {
      key: "v_cmd",
      label: "v_cmd",
      value: m.vCmd == null ? "—" : m.vCmd.toFixed(1),
      unit: "m/s",
      bar: m.vCmd == null ? undefined : Math.min(1, m.vCmd / 25),
    },
    {
      key: "accel",
      label: "accel",
      value: m.accel == null ? "—" : m.accel.toFixed(2),
      unit: "m/s²",
      bar: accelBar ?? undefined,
      tone: m.accel != null && m.accel < -1.5 ? "warn" : undefined,
    },
    {
      key: "steer",
      label: "steer",
      value: m.steer == null ? "—" : m.steer.toFixed(2),
      bar: steerAbs ?? undefined,
    },
    {
      key: "d_gap",
      label: "d_gap",
      value: m.dGap == null ? "—" : m.dGap.toFixed(1),
      unit: "m",
      tone: m.dGap != null && m.dGap < 8 ? "warn" : undefined,
    },
    {
      key: "ttc",
      label: "TTC",
      value: m.ttc == null ? "—" : m.ttc.toFixed(1),
      unit: "s",
      tone:
        m.ttc != null && m.ttc < 1.5
          ? "danger"
          : m.ttc != null && m.ttc < 2.8
            ? "warn"
            : undefined,
    },
    {
      key: "lat",
      label: "lat_err",
      value: m.latErrM == null ? "—" : m.latErrM.toFixed(2),
      unit: "m",
      tone: m.latErrM != null && Math.abs(m.latErrM) > 0.4 ? "warn" : undefined,
    },
    {
      key: "hands",
      label: "hands_off",
      value: m.handsOffS == null ? "—" : m.handsOffS.toFixed(1),
      unit: "s",
      bar: handsBar ?? undefined,
      tone:
        m.handsOffS != null && m.handsOffS >= m.handsOffTorS
          ? "danger"
          : m.handsOffS != null && m.handsOffS >= m.handsOffWarnS
            ? "warn"
            : undefined,
    },
  ];
}

/** 底栏通道条：工程师扫一眼关键标量 */
export function ChannelStrip({ metrics, collapsed, onToggle }: Props) {
  const cells = cellsOf(metrics);
  return (
    <footer className={`channel-strip${collapsed ? " collapsed" : ""}`}>
      <button
        type="button"
        className="channel-toggle"
        onClick={onToggle}
        title={collapsed ? "展开通道条" : "折叠通道条"}
      >
        {collapsed ? "通道 ▴" : "通道 ▾"}
      </button>
      {!collapsed ? (
        <div className="channel-cells">
          {cells.map((c) => (
            <div
              key={c.key}
              className={`channel-cell${c.tone ? ` ${c.tone}` : ""}`}
            >
              <div className="channel-label">{c.label}</div>
              <div className="channel-value">
                {c.value}
                {c.unit ? <span className="channel-unit"> {c.unit}</span> : null}
              </div>
              {c.bar != null ? (
                <div className="channel-bar">
                  <span style={{ width: `${(c.bar * 100).toFixed(0)}%` }} />
                </div>
              ) : (
                <div className="channel-bar empty" />
              )}
            </div>
          ))}
        </div>
      ) : null}
    </footer>
  );
}
