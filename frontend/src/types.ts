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
export type MovementTarget = "auto" | "virtual" | "physical" | "both";
export type RobotActivationMode = "ready" | "armed";

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
  movement_target?: MovementTarget;
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
  movement_target: MovementTarget;
  virtual_applied: boolean;
  physical_applied: boolean;
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

export interface ObjectPickupStartRequest {
  operator_id?: string;
  operator_confirmed: boolean;
  object_label?: string;
  reason?: string;
}

export interface ObjectPickupFinishRequest {
  session_id?: string | null;
  operator_id?: string;
  save_as_template?: boolean;
  reason?: string;
}

export interface ObjectPickupReplayRequest {
  session_id: string;
  operator_id?: string;
  operator_confirmed: boolean;
  reason?: string;
}

export interface CameraStream {
  twin_id: string;
  robot_id: string;
  source_url: string;
  browser_url: string;
  status: string;
}

export interface CyberwaveRobot {
  twin_uuid: string;
  name: string;
  robot_id: string;
  registry_id: string | null;
  slug: string | null;
  has_stream: boolean;
  stream_url: string | null;
  browser_url: string | null;
  available_actions: string[];
  source: string;
  discovered_at: string;
}

export interface RobotActivationRequest {
  operator_id?: string;
  operator_confirmed: boolean;
  activation_mode: RobotActivationMode;
  allow_physical: boolean;
  reason?: string;
}

export interface RobotActivationState {
  robot_id: string;
  available: boolean;
  ready: boolean;
  armed: boolean;
  activation_mode: RobotActivationMode | null;
  physical_enabled: boolean;
  virtual_enabled: boolean;
  operator_id: string | null;
  reason: string | null;
  last_check: string;
}

export interface ObjectPickupStep {
  step_id: string;
  step_type: string;
  robot_id: string;
  action: string;
  data: Record<string, unknown>;
  camera_streams: CameraStream[];
  recorded_at: string;
}

export interface ObjectPickupSession {
  session_id: string;
  object_label: string;
  operator_id: string;
  status: "recording" | "saved" | "replayed";
  go2_posture_action: string;
  camera_streams: CameraStream[];
  steps: ObjectPickupStep[];
  reason: string;
  replay_count: number;
  started_at: string;
  finished_at: string | null;
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
  cyberwave_robots: CyberwaveRobot[];
  robot_activations: RobotActivationState[];
  scout_route: ScoutRouteResult | null;
  object_pickup_sessions: ObjectPickupSession[];
  active_object_pickup_session: ObjectPickupSession | null;
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
