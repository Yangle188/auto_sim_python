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

export interface Snapshot {
  t: number;
  state: string;
  vehicle: VehicleState;
  vehicle_est?: VehicleState;
  waypoints: Point[];
  path: Point[];
  lookahead: Point | null;
  lane_width?: number;
  num_lanes?: number;
  lane_left?: Point[];
  lane_right?: Point[];
  lane_markings?: LaneMarking[];
  vehicle_geom?: VehicleGeom;
  obstacles: { x: number; y: number; width: number; height: number }[];
  fused: { x: number; y: number; source?: string }[];
  predictions: { trajectory: Point[]; coasting?: boolean; vx?: number; vy?: number }[];
  v_cmd: number;
  steer: number;
  speed_limit: number | null;
  acc?: { d_gap: number; v_lead: number; source: string } | null;
  route_links: RouteLink[];
  session_status?: string;
  view?: { mode?: string };
}

export interface StatusPayload {
  status: string;
  t: number;
  duration_s: number;
}

export interface PresetMeta {
  id: string;
  title: string;
  description: string;
}
