export type Point = [number, number];

export type RoadClass = "main" | "aux";
export type Maneuver = "straight" | "left" | "right" | "merge" | "diverge";

export interface RouteLink {
  link_id: string;
  points: Point[];
  speed_limit: number;
  name?: string;
  road_class?: RoadClass;
  maneuver?: Maneuver;
}

export interface LinearMotion {
  type: "linear";
  vx: number;
  vy: number;
  x0: number;
  y0: number;
}

export interface MotionKeyframe {
  t: number;
  x: number;
  y: number;
}

export interface ScriptedMotion {
  type: "scripted";
  keyframes: MotionKeyframe[];
}

export type Motion = LinearMotion | ScriptedMotion;

export interface ObstacleIn {
  x: number;
  y: number;
  width: number;
  height: number;
  dynamic: boolean;
  motion: Motion | null;
}

export interface SceneConfig {
  route_id: string;
  links: RouteLink[];
  obstacles: ObstacleIn[];
  duration_s: number;
  base_map_id?: string | null;
  lane_map_id?: string | null;
  start_lane_index?: number;
}

export interface VehicleState {
  x: number;
  y: number;
  yaw: number;
  speed: number;
}

export interface VehicleGeom {
  width: number;
  length: number;
  wheel_base: number;
  rear_overhang: number;
  front_overhang?: number;
  ref_point: string;
  lane_width: number;
  num_lanes?: number;
}

export interface LaneMarking {
  role: string;
  style: "solid" | "dashed" | string;
  points: Point[];
}

export interface HmiAlert {
  level: string;
  msg: string;
  code?: string;
  t?: number;
}

export interface HmiPayload {
  ad_state: string;
  alerts: HmiAlert[];
  latest?: HmiAlert | null;
  highest?: string;
}

export interface Snapshot {
  t: number;
  state: string;
  vehicle: VehicleState;
  vehicle_est?: VehicleState;
  waypoints: Point[];
  path: Point[];
  lookahead: Point | null;
  /** 沿参考路径到预瞄点 */
  lookahead_path?: Point[];
  /** Pure Pursuit 圆弧预瞄轨迹 */
  preview_traj?: Point[];
  lookahead_dist?: number;
  lane_width?: number;
  num_lanes?: number;
  lane_left?: Point[];
  lane_right?: Point[];
  lane_markings?: LaneMarking[];
  /** 底图全网车道线（导航场景） */
  network_lane_markings?: LaneMarking[];
  base_map_id?: string | null;
  lane_map_id?: string | null;
  ego_lane_id?: string | null;
  lane_index?: number | null;
  ego_lane_centerline?: Point[];
  use_world_lanes?: boolean;
  lane_change?: {
    state?: string;
    ego_lane_id?: string;
    target_lane_id?: string | null;
    direction?: string;
    lane_index?: number | null;
  };
  aeb?: { mode?: string; d_gap?: number | null; ttc?: number | null };
  vehicle_geom?: VehicleGeom;
  obstacles: { x: number; y: number; width: number; height: number }[];
  fused: { x: number; y: number; source?: string }[];
  predictions: { trajectory: Point[]; coasting?: boolean; vx?: number; vy?: number }[];
  v_cmd: number;
  steer: number;
  /** 纵向加速度指令 (m/s²) */
  accel?: number;
  speed_limit: number | null;
  acc?: { d_gap: number; v_lead: number; source: string } | null;
  route_links: RouteLink[];
  session_status?: string;
  view?: { mode?: string; cam_yaw?: number; lock_road_heading?: boolean };
  hmi?: HmiPayload;
}

export interface StatusPayload {
  status: string;
  t: number;
  duration_s: number;
  frame_i?: number;
  frame_n?: number;
  /** 整段 episode 预期帧数（时间轴刻度） */
  frame_total?: number;
  scrubbing?: boolean;
  /** 自动驾驶状态机 */
  ad_state?: string;
  ad_engage_pending?: boolean;
  can_activate?: boolean;
  can_deactivate?: boolean;
  can_lane_change?: boolean;
  lane_change?: {
    state?: string;
    ego_lane_id?: string;
    target_lane_id?: string | null;
    direction?: string;
    lane_index?: number | null;
  };
}

export interface PresetMeta {
  id: string;
  title: string;
  description: string;
}

export interface BaseMapNode {
  node_id: string;
  x: number;
  y: number;
  name?: string;
}

export interface BaseMapEdge {
  edge_id: string;
  from_node: string;
  to_node: string;
  points: Point[];
  speed_limit: number;
  name?: string;
  road_class?: RoadClass;
  maneuver?: Maneuver;
  length?: number;
}

export interface BaseMapData {
  map_id: string;
  title: string;
  nodes: BaseMapNode[];
  edges: BaseMapEdge[];
  lane_markings?: LaneMarking[];
}
