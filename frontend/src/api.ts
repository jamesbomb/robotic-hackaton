import type {
  BaseMovementCommandRequest,
  BaseMovementResult,
  EventRecord,
  ManualArmCommandRequest,
  ManualArmResult,
  MissionReport,
  MissionSnapshot,
  RobotStatus,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export function getSnapshot() {
  return request<MissionSnapshot>("/api/snapshot");
}

export function getRobots() {
  return request<RobotStatus[]>("/api/robots");
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

export function sendCommand(text: string, scenario: string) {
  return request<MissionReport>("/api/commands", {
    method: "POST",
    body: JSON.stringify({ text, scenario }),
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

export function connectEvents(onEvent: (event: EventRecord) => void) {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${window.location.host}/ws/events`);
  socket.addEventListener("message", (message) => {
    onEvent(JSON.parse(message.data) as EventRecord);
  });
  return socket;
}
