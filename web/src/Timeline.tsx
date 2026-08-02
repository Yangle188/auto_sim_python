import type { CSSProperties } from "react";

interface Props {
  frameI: number;
  frameN: number;
  /** 整段仿真预期总帧数；用于进度条分母，避免直播时永远停在末端 */
  frameTotal: number;
  t: number;
  durationS: number;
  scrubbing: boolean;
  disabled: boolean;
  onSeek: (frameI: number) => void;
}

export function Timeline({
  frameI,
  frameN,
  frameTotal,
  t,
  durationS,
  scrubbing,
  disabled,
  onSeek,
}: Props) {
  const total = Math.max(1, frameTotal, frameN);
  const max = total - 1;
  // 未开跑时停在起点；直播时 frameI 随时间增长，相对 total 前进
  const value = frameN <= 0 || frameI < 0 ? 0 : Math.max(0, Math.min(max, frameI));
  const pct = max <= 0 ? 0 : (value / max) * 100;
  const recordedMax = Math.max(0, frameN - 1);
  const recordedPct = max <= 0 ? 0 : (recordedMax / max) * 100;
  const rangeStyle = {
    ["--pct" as string]: `${pct}%`,
    ["--recorded" as string]: `${recordedPct}%`,
  } as CSSProperties;

  return (
    <div className={`timeline${scrubbing ? " scrubbing" : ""}`}>
      <div className="timeline-meta">
        <span>时间轴</span>
        <span className="timeline-t">
          t={t.toFixed(2)}s / {durationS.toFixed(0)}s
          {frameN > 0 ? ` · 帧 ${value + 1}/${frameN}` : " · 暂无帧"}
          {scrubbing ? " · 回看中" : ""}
        </span>
      </div>
      <div className="timeline-track-wrap">
        <input
          className="timeline-range"
          type="range"
          min={0}
          max={max}
          step={1}
          value={value}
          disabled={disabled || frameN <= 0}
          onChange={(e) => {
            const want = Number(e.target.value);
            // 只能跳到已录制区间
            onSeek(Math.max(0, Math.min(recordedMax, want)));
          }}
          style={rangeStyle}
          aria-label="仿真时间轴"
        />
      </div>
    </div>
  );
}
