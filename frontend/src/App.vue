<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import {
  activateRobot,
  connectEvents,
  finishObjectPickup,
  getSnapshot,
  markLatestObject,
  replayObjectPickup,
  sendBaseMovementCommand,
  sendCommand,
  sendManualArmCommand,
  sendScoutRoutePlan,
  startMission,
  startObjectPickup,
  stopMission,
  updateRuntime,
} from "./api";
import type {
  BaseMovementCommandRequest,
  BaseMovementResult,
  CameraStream,
  ClassificationLabel,
  CyberwaveRobot,
  EventRecord,
  ManualArmCommandRequest,
  ManualArmResult,
  MapPoint,
  MissionReport,
  MissionSnapshot,
  ObjectPickupSession,
  RobotActivationRequest,
  RobotActivationState,
  RobotStatus,
  RuntimeConfigRequest,
  RuntimeStatus,
  ScoutRouteResult,
} from "./types";
import BaseMovementPanel from "./components/BaseMovementPanel.vue";
import CameraPanel from "./components/CameraPanel.vue";
import ClassificationCard from "./components/ClassificationCard.vue";
import CommandPalette from "./components/CommandPalette.vue";
import EventTimeline from "./components/EventTimeline.vue";
import ManualArmPanel from "./components/ManualArmPanel.vue";
import MissionHeader from "./components/MissionHeader.vue";
import ObjectPickupPanel from "./components/ObjectPickupPanel.vue";
import RiskMap from "./components/RiskMap.vue";
import RobotActivationPanel from "./components/RobotActivationPanel.vue";
import RobotFleetPanel from "./components/RobotFleetPanel.vue";
import SafetyControls from "./components/SafetyControls.vue";
import ScoutPathPlanner from "./components/ScoutPathPlanner.vue";

const snapshot = ref<MissionSnapshot | null>(null);
const report = ref<MissionReport | null>(null);
const robots = ref<RobotStatus[]>([]);
const events = ref<EventRecord[]>([]);
const cameraStreams = ref<CameraStream[]>([]);
const cyberwaveRobots = ref<CyberwaveRobot[]>([]);
const robotActivations = ref<RobotActivationState[]>([]);
const scoutRoute = ref<ScoutRouteResult | null>(null);
const objectPickupSessions = ref<ObjectPickupSession[]>([]);
const activeObjectPickupSession = ref<ObjectPickupSession | null>(null);
const runtimeStatus = ref<RuntimeStatus | null>(null);
const manualArmResult = ref<ManualArmResult | null>(null);
const baseMovementResult = ref<BaseMovementResult | null>(null);
const busy = ref(false);
const error = ref<string | null>(null);
let socket: WebSocket | null = null;

const missionState = computed(() => snapshot.value?.mission?.state ?? report.value?.state ?? "IDLE");
const runtimeMode = computed(() => runtimeStatus.value?.runtime_mode ?? "mock");
const dryRun = computed(() => runtimeStatus.value?.dry_run ?? true);
const liveAdapterReady = computed(() => runtimeStatus.value?.live_adapter_ready ?? false);
const runtimeNote = computed(() => runtimeStatus.value?.note ?? "Runtime status unavailable.");
const observations = computed(() => report.value?.observations ?? []);
const latestObservation = computed(() => observations.value.at(-1) ?? null);
const finding = computed(() => report.value?.finding ?? null);
const so101 = computed(() => robots.value.find((robot) => robot.robot_id === "so101") ?? null);

async function refresh() {
  snapshot.value = await getSnapshot();
  report.value = snapshot.value.report;
  robots.value = snapshot.value.robots;
  events.value = snapshot.value.events;
  cameraStreams.value = snapshot.value.camera_streams;
  cyberwaveRobots.value = snapshot.value.cyberwave_robots;
  robotActivations.value = snapshot.value.robot_activations;
  scoutRoute.value = snapshot.value.scout_route;
  objectPickupSessions.value = snapshot.value.object_pickup_sessions;
  activeObjectPickupSession.value = snapshot.value.active_object_pickup_session;
  runtimeStatus.value = snapshot.value.runtime;
}

async function runAction(action: () => Promise<MissionReport>) {
  busy.value = true;
  error.value = null;
  try {
    report.value = await action();
    await refresh();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Unknown error";
  } finally {
    busy.value = false;
  }
}

async function runManualArmTakeover(robotId: string, command: ManualArmCommandRequest) {
  busy.value = true;
  error.value = null;
  try {
    manualArmResult.value = await sendManualArmCommand(robotId, command);
    await refresh();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Unknown error";
  } finally {
    busy.value = false;
  }
}

async function runBaseMovement(robotId: string, command: BaseMovementCommandRequest) {
  busy.value = true;
  error.value = null;
  try {
    baseMovementResult.value = await sendBaseMovementCommand(robotId, command);
    await refresh();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Unknown error";
  } finally {
    busy.value = false;
  }
}

async function runRobotActivation(robotId: string, command: RobotActivationRequest) {
  busy.value = true;
  error.value = null;
  try {
    await activateRobot(robotId, command);
    await refresh();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Unknown error";
  } finally {
    busy.value = false;
  }
}

async function runRuntimeChange(command: RuntimeConfigRequest) {
  busy.value = true;
  error.value = null;
  try {
    runtimeStatus.value = await updateRuntime(command);
    await refresh();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Unknown error";
  } finally {
    busy.value = false;
  }
}

async function markCameraObject(label: ClassificationLabel) {
  await runAction(() =>
    markLatestObject({
      label,
      operator_id: "operator",
      reason: "Operator marked object from camera panel.",
    }),
  );
}

async function planScoutRoute(waypoints: MapPoint[]) {
  busy.value = true;
  error.value = null;
  try {
    scoutRoute.value = await sendScoutRoutePlan({
      robot_id: "go2",
      operator_confirmed: true,
      waypoints,
      reason: "Operator planned scout path from dashboard map.",
    });
    await refresh();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Unknown error";
  } finally {
    busy.value = false;
  }
}

async function runObjectPickupStart(operatorId: string, objectLabel: string) {
  busy.value = true;
  error.value = null;
  try {
    activeObjectPickupSession.value = await startObjectPickup({
      operator_id: operatorId,
      object_label: objectLabel,
      operator_confirmed: true,
      reason: "Operator started assisted object pickup recording from dashboard.",
    });
    await refresh();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Unknown error";
  } finally {
    busy.value = false;
  }
}

async function runObjectPickupFinish(sessionId: string | null) {
  busy.value = true;
  error.value = null;
  try {
    await finishObjectPickup({
      session_id: sessionId,
      operator_id: "operator",
      save_as_template: true,
      reason: "Operator saved assisted object pickup recording from dashboard.",
    });
    await refresh();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Unknown error";
  } finally {
    busy.value = false;
  }
}

async function runObjectPickupReplay(sessionId: string, operatorId: string) {
  busy.value = true;
  error.value = null;
  try {
    await replayObjectPickup({
      session_id: sessionId,
      operator_id: operatorId,
      operator_confirmed: true,
      reason: "Operator selected recorded pickup template from dashboard.",
    });
    await refresh();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Unknown error";
  } finally {
    busy.value = false;
  }
}

function onEvent(event: EventRecord) {
  events.value = [...events.value, event].slice(-200);
}

onMounted(async () => {
  await refresh();
  socket = connectEvents(onEvent);
});

onUnmounted(() => {
  socket?.close();
});
</script>

<template>
  <main class="app-shell">
    <MissionHeader
      :state="missionState"
      :runtime-mode="runtimeMode"
      :dry-run="dryRun"
      :busy="busy"
      @start="(scenario) => runAction(() => startMission(scenario))"
      @stop="() => runAction(stopMission)"
    />

    <p v-if="error" class="error-banner">{{ error }}</p>

    <div class="console-grid">
      <aside class="left-rail">
        <RobotFleetPanel :robots="robots" />
        <RobotActivationPanel
          :cyberwave-robots="cyberwaveRobots"
          :activations="robotActivations"
          :runtime-mode="runtimeMode"
          :dry-run="dryRun"
          :busy="busy"
          @activate="(robotId, command) => runRobotActivation(robotId, command)"
        />
        <SafetyControls
          :dry-run="dryRun"
          :runtime-mode="runtimeMode"
          :live-adapter-ready="liveAdapterReady"
          :runtime-note="runtimeNote"
          :busy="busy"
          @runtime-change="(command) => runRuntimeChange(command)"
          @stop="() => runAction(stopMission)"
        />
        <BaseMovementPanel
          :robots="robots"
          :activations="robotActivations"
          :runtime-mode="runtimeMode"
          :dry-run="dryRun"
          :busy="busy"
          @move="(robotId, command) => runBaseMovement(robotId, command)"
          @stop="() => runAction(stopMission)"
        />
        <p v-if="baseMovementResult" class="subtle">
          Last base move: {{ baseMovementResult.robot_id }} /
          {{ baseMovementResult.action }}
        </p>
        <ManualArmPanel
          :robot="so101"
          :busy="busy"
          @manual-command="(robotId, command) => runManualArmTakeover(robotId, command)"
        />
        <p v-if="manualArmResult" class="subtle">
          Last SO-101 command: {{ manualArmResult.action }} /
          {{ manualArmResult.applied ? "applied" : "rejected" }}
        </p>
      </aside>

      <section class="center-stage">
        <RiskMap :robots="robots" :observations="observations" :finding="finding" />
        <ScoutPathPlanner :busy="busy" :route="scoutRoute" @plan="planScoutRoute" />
        <CameraPanel
          :observation="latestObservation"
          :streams="cameraStreams"
          :runtime-mode="runtimeMode"
          @mark="(label) => markCameraObject(label)"
        />
        <ObjectPickupPanel
          :active-session="activeObjectPickupSession"
          :sessions="objectPickupSessions"
          :busy="busy"
          @start="(operatorId, objectLabel) => runObjectPickupStart(operatorId, objectLabel)"
          @finish="(sessionId) => runObjectPickupFinish(sessionId)"
          @replay="(sessionId, operatorId) => runObjectPickupReplay(sessionId, operatorId)"
        />
      </section>

      <aside class="right-rail">
        <ClassificationCard :report="report" />
        <CommandPalette @command="(text, scenario) => runAction(() => sendCommand(text, scenario))" />
        <EventTimeline :events="events" />
      </aside>
    </div>
  </main>
</template>
