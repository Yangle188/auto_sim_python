import type { ReactNode } from "react";

interface Props {
  /** SideDock 悬停时为 false → Canvas pointer-events:none */
  canvasInteractive: boolean;
  children: ReactNode;
  /** 仪表簇等 PIP（pointer-events 独立，不挡 BEV 拖拽区域外点击） */
  pip?: ReactNode;
  overlay?: ReactNode;
}

/**
 * 主视口容器：根据 SideDock 悬停动态切断 BEV 指针事件，避免右栏干扰视角。
 */
export function ViewportHost({
  canvasInteractive,
  children,
  pip,
  overlay,
}: Props) {
  return (
    <section className="viewport-host stage">
      <div className="stage-with-hmi">
        <div
          className="viewport-canvas-slot"
          style={{ pointerEvents: canvasInteractive ? "auto" : "none" }}
        >
          {children}
        </div>
        {pip ? <div className="viewport-pip">{pip}</div> : null}
        {overlay}
      </div>
    </section>
  );
}
