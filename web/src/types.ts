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

export interface ObstacleIn {
  x: number;
  y: number;
  width: number;
  height: number;
  dynamic: boolean;
  motion: LinearMotion | null;
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
  lane_left?: Point[];
  lane_right?: Point[];
  vehicle_geom?: VehicleGeom;
  obstacles: { x: number; y: number; width: number; height: number }[];
  fused: { x: number; y: number; source?: string }[];
  predictions: { trajectory: Point[]; coasting?: boolean }[];
  v_cmd: number;
  steer: number;
  speed_limit: number | null;
  route_links: RouteLink[];
  session_status?: string;
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
