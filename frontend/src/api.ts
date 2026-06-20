import type {
  BaseMovementCommandRequest,
  BaseMovementResult,
  CameraStream,
  CyberwaveRobot,
  EventRecord,
  FrameClassificationResult,
  ManualArmCommandRequest,
  ManualArmResult,
  MissionReport,
  MovementCommandRequest,
  MovementCommandResult,
  ObjectMarkRequest,
  ObjectPickupFinishRequest,
  ObjectPickupReplayRequest,
  ObjectPickupSession,
  ObjectPickupStartRequest,
  MissionSnapshot,
  RobotActivationRequest,
  RobotActivationState,
  RobotStatus,
  RuntimeConfigRequest,
  RuntimeStatus,
  ScoutRouteCommandRequest,
  ScoutRouteResult,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : response.statusText;
    throw new Error(`${response.status} ${detail}`);
  }
  return response.json() as Promise<T>;
}

export function classifyRobotFrame(robotId: string) {
  return request<FrameClassificationResult>(`/api/robots/${robotId}/classify-frame`, {
    method: "POST",
  });
}

export function getSnapshot() {
  return request<MissionSnapshot>("/api/snapshot");
}

export function getRuntime() {
  return request<RuntimeStatus>("/api/runtime");
}

export function updateRuntime(command: RuntimeConfigRequest) {
  return request<RuntimeStatus>("/api/runtime", {
    method: "POST",
    body: JSON.stringify(command),
  });
}

export function getRobots() {
  return request<RobotStatus[]>("/api/robots");
}

export function getCameraStreams() {
  return request<CameraStream[]>("/api/camera-streams");
}

export function getCyberwaveRobots() {
  return request<CyberwaveRobot[]>("/api/cyberwave/robots");
}

export function activateRobot(robotId: string, command: RobotActivationRequest) {
  return request<RobotActivationState>(`/api/robots/${robotId}/activate`, {
    method: "POST",
    body: JSON.stringify(command),
  });
}

export function getObjectPickupSessions() {
  return request<ObjectPickupSession[]>("/api/object-pickup/sessions");
}

export function startObjectPickup(command: ObjectPickupStartRequest) {
  return request<ObjectPickupSession>("/api/object-pickup/start", {
    method: "POST",
    body: JSON.stringify(command),
  });
}

export function finishObjectPickup(command: ObjectPickupFinishRequest) {
  return request<ObjectPickupSession>("/api/object-pickup/finish", {
    method: "POST",
    body: JSON.stringify(command),
  });
}

export function replayObjectPickup(command: ObjectPickupReplayRequest) {
  return request<ObjectPickupSession>("/api/object-pickup/replay", {
    method: "POST",
    body: JSON.stringify(command),
  });
}

export function getEvents() {
  return request<EventRecord[]>("/api/events");
}

export function startMission(scenario: string) {
  return request<MissionReport>("/api/missions/start", {
    method: "POST",
    body: JSON.stringify({ scenario }),
  });
}

export function stopMission() {
  return request<MissionReport>("/api/missions/stop", { method: "POST" });
}

export function stopRobot(robotId: string) {
  return request<RobotStatus[]>(`/api/robots/${robotId}/stop`, { method: "POST" });
}

export function sendCommand(text: string, scenario: string) {
  return request<MissionReport>("/api/commands", {
    method: "POST",
    body: JSON.stringify({ text, scenario }),
  });
}

export function markLatestObject(command: ObjectMarkRequest) {
  return request<MissionReport>("/api/observations/mark", {
    method: "POST",
    body: JSON.stringify(command),
  });
}

export function sendManualArmCommand(robotId: string, command: ManualArmCommandRequest) {
  return request<ManualArmResult>(`/api/robots/${robotId}/manual-arm`, {
    method: "POST",
    body: JSON.stringify(command),
  });
}

export function sendBaseMovementCommand(robotId: string, command: BaseMovementCommandRequest) {
  return request<BaseMovementResult>(`/api/robots/${robotId}/move`, {
    method: "POST",
    body: JSON.stringify(command),
  });
}

export function sendGo2MovementCommand(command: MovementCommandRequest) {
  return request<MovementCommandResult>("/api/robots/go2/movement-command", {
    method: "POST",
    body: JSON.stringify(command),
  });
}

export function sendScoutRoutePlan(command: ScoutRouteCommandRequest) {
  return request<ScoutRouteResult>("/api/robots/go2/route-plan", {
    method: "POST",
    body: JSON.stringify(command),
  });
}

export function connectEvents(onEvent: (event: EventRecord) => void) {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${window.location.host}/ws/events`);
  socket.addEventListener("message", (message) => {
    onEvent(JSON.parse(message.data) as EventRecord);
  });
  return socket;
}
