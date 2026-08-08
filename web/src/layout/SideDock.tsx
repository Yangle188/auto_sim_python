import type { ReactNode } from "react";

export type DockTab = "mission" | "scene" | "events";

interface Props {
  tab: DockTab;
  onTab: (t: DockTab) => void;
  onHoverChange: (hovering: boolean) => void;
  mission: ReactNode;
  scene: ReactNode;
  events: ReactNode;
}

const TABS: { id: DockTab; label: string }[] = [
  { id: "mission", label: "Mission" },
  { id: "scene", label: "Scene" },
  { id: "events", label: "Events" },
];

/**
 * 右侧停靠栏：移入/移出通知 ViewportHost，用于 Canvas pointer-events。
 */
export function SideDock({
  tab,
  onTab,
  onHoverChange,
  mission,
  scene,
  events,
}: Props) {
  return (
    <div
      className="side-dock"
      onMouseEnter={() => onHoverChange(true)}
      onMouseLeave={() => onHoverChange(false)}
    >
      <div className="dock-tabs" role="tablist" aria-label="侧栏">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            className={`dock-tab${tab === t.id ? " active" : ""}`}
            onClick={() => onTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="dock-body" role="tabpanel">
        {tab === "mission" ? mission : null}
        {tab === "scene" ? scene : null}
        {tab === "events" ? events : null}
      </div>
    </div>
  );
}
