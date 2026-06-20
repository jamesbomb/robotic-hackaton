export type MissionState =
  | "IDLE"
  | "OBSERVE"
  | "CLASSIFY"
  | "REPORT"
  | "MANUAL_STOP"
  | "ERROR_SAFE"
  | "UNCERTAIN"
  | "SECOND_OBSERVATION"
  | "CONSENSUS"
  | "HUMAN_REVIEW";

export type ClassificationLabel = "MINE" | "NOT_MINE" | "UNCERTAIN";

export interface RobotPose {
  x: number;
  y: number;
  yaw: number;
}

export interface RobotStatus {
  robot_id: string;
  role: string;
  online: boolean;
  mode: "mock" | "simulation" | "live";
  task: string;
  battery_percent: number | null;
  sensors: string[];
  actions: string[];
  heartbeat_at: string;
  pose: RobotPose;
  note: string | null;
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
}

export interface MissionSnapshot {
  mission: { mission_id: string; state: MissionState; runtime_mode: string; dry_run: boolean } | null;
  report: MissionReport | null;
  robots: RobotStatus[];
  events: EventRecord[];
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
