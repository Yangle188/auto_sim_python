import type { BaseMapData, SceneConfig, Snapshot } from "../types";
import type { EditTool } from "../sceneEdit";

/** BEV 相机：每帧由 Viewport 从 refs 组装，图层只读 */
export interface Camera {
  cssW: number;
  cssH: number;
  dpr: number;
  zoom: number;
  panX: number;
  panY: number;
  editTool: EditTool;
}

/**
 * 原始帧/编辑输入。调用 paint 前不得裁剪、过滤或派生新 scene。
 * trail 为视口私有缓冲引用，可在 paint 内追加。
 */
export interface FrameData {
  snapshot: Snapshot | null;
  draft: SceneConfig;
  baseMap: BaseMapData | null;
  navStart: string | null;
  navEnd: string | null;
  selectedLinkIdx: number;
  selectedObstacleIdx: number | null;
  paused: boolean;
  trail: [number, number][];
  trailEst: [number, number][];
}

export type LayerFlags = Record<string, boolean>;

export const DEFAULT_LAYER_FLAGS: LayerFlags = {
  "map.network": true,
  "map.junctions": true,
  "route.nav": true,
  "plan.path": true,
  "plan.nudge": true,
  "plan.lane_change": true,
  "ctrl.pp_preview": true,
  "perc.fused": true,
  "perc.truth_obstacles": true,
  "pred.traj": true,
  "ego.truth": true,
  "ego.est": true,
  "ego.trail": true,
  "debug.grid": true,
  "debug.ids": false,
  "debug.hud": true,
};
