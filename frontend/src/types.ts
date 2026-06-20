export type MissionState =
  | "IDLE"
  | "OBSERVE"
  | "CLASSIFY"
  | "REPORT"
  | "MANUAL_STOP"
  | "MANUAL_TAKEOVER"
  | "ERROR_SAFE"
  | "UNCERTAIN"
  | "SECOND_OBSERVATION"
  | "CONSENSUS"
  | "HUMAN_REVIEW";

export type ClassificationLabel = "MINE" | "NOT_MINE" | "UNCERTAIN";
export type ManualArmAction = "home" | "hold_position" | "nudge_joint" | "place_safe_marker";
export type BaseMovementAction = "move_forward" | "move_backward" | "rotate_left" | "rotate_right";
export type RuntimeMode = "mock" | "simulation" | "live";

export interface RobotPose {
  x: number;
  y: number;
  yaw: number;
}

export interface RobotStatus {
  robot_id: string;
  role: string;
  online: boolean;
  mode: RuntimeMode;
  task: string;
  battery_percent: number | null;
  sensors: string[];
  actions: string[];
  heartbeat_at: string;
  pose: RobotPose;
  note: string | null;
}

export interface RuntimeConfigRequest {
  runtime_mode: RuntimeMode;
  dry_run: boolean;
  operator_id?: string;
  operator_confirmed: boolean;
  reason?: string;
}

export interface RuntimeStatus {
  runtime_mode: RuntimeMode;
  dry_run: boolean;
  live_adapter_ready: boolean;
  note: string;
}

export interface ManualArmCommandRequest {
  action: ManualArmAction;
  operator_id?: string;
  operator_confirmed: boolean;
  joint_name?: string | null;
  delta_degrees?: number;
  target_label?: ClassificationLabel | null;
  reason?: string;
}

export interface ManualArmResult {
  command_id: string;
  robot_id: string;
  action: ManualArmAction;
  applied: boolean;
  dry_run: boolean;
  joint_name: string | null;
  joint_positions_degrees: Record<string, number>;
  executed_sequence: string[];
  reason: string;
}

export interface BaseMovementCommandRequest {
  action: BaseMovementAction;
  operator_id?: string;
  operator_confirmed: boolean;
  distance_m?: number;
  angle_degrees?: number;
  reason?: string;
}

export interface BaseMovementResult {
  command_id: string;
  robot_id: string;
  action: BaseMovementAction;
  applied: boolean;
  dry_run: boolean;
  pose: RobotPose;
  executed_sequence: string[];
  reason: string;
}

export interface MapPoint {
  x: number;
  y: number;
}

export interface MapObstacle {
  obstacle_id: string;
  label: string;
  position: MapPoint;
  radius: number;
  source: string;
}

export interface ScoutRouteCommandRequest {
  robot_id?: string;
  operator_id?: string;
  operator_confirmed: boolean;
  waypoints: MapPoint[];
  reason?: string;
}

export interface ScoutRouteResult {
  route_id: string;
  robot_id: string;
  accepted: boolean;
  dry_run: boolean;
  waypoints: MapPoint[];
  point_map: MapPoint[];
  obstacles: MapObstacle[];
  reason: string;
}

export interface CameraStream {
  twin_id: string;
  robot_id: string;
  source_url: string;
  browser_url: string;
  status: string;
}

export interface FrameRef {
  frame_id: string;
  sensor_id: string;
  source: "fixture" | "camera" | "cyberwave";
  path: string;
  captured_at: string;
  width: number | null;
  height: number | null;
  metadata: Record<string, unknown>;
}

export interface ClassificationResult {
  label: ClassificationLabel;
  confidence: number;
  bbox: number[] | null;
  evidence: string[];
  recommended_action: "REPORT" | "SECOND_VIEW" | "HUMAN_REVIEW";
}

export interface ObjectMarkRequest {
  label: ClassificationLabel;
  operator_id?: string;
  reason?: string;
}

export interface Observation {
  observation_id: string;
  mission_id: string;
  robot_id: string;
  sensor_id: string;
  sector: string | null;
  pose: RobotPose;
  frame: FrameRef;
  classification: ClassificationResult;
  observed_at: string;
}

export interface Finding {
  finding_id: string;
  mission_id: string;
  sector: string | null;
  label: ClassificationLabel;
  confidence: number;
  safe_to_contact: boolean;
  observations: string[];
  rationale: string;
  updated_at: string;
}

export interface MissionReport {
  mission_id: string;
  state: MissionState;
  frame: FrameRef | null;
  classification: ClassificationResult | null;
  recommendation: string | null;
  safe_to_contact: boolean;
  summary: string;
  observations: Observation[];
  finding: Finding | null;
  route_trace?: unknown;
}

export interface MissionSnapshot {
  mission: { mission_id: string; state: MissionState; runtime_mode: RuntimeMode; dry_run: boolean } | null;
  runtime: RuntimeStatus;
  report: MissionReport | null;
  robots: RobotStatus[];
  events: EventRecord[];
  camera_streams: CameraStream[];
  scout_route: ScoutRouteResult | null;
}

export interface EventRecord {
  mission_id: string;
  event_type: string;
  timestamp: string;
  state: MissionState | null;
  robot_id: string | null;
  sensor_id: string | null;
  frame_path: string | null;
  data: Record<string, unknown>;
}
