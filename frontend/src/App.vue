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
  sendGo2MovementCommand,
  sendManualArmCommand,
  sendScoutRoutePlan,
  startMission,
  startObjectPickup,
  stopMission,
  stopRobot,
  updateRuntime,
} from "./api";
import type {
  BaseMovementCommandRequest,
  BaseMovementAction,
  BaseMovementResult,
  CameraSource,
  CameraStream,
  ClassificationLabel,
  CyberwaveRobot,
  EventRecord,
  ManualArmCommandRequest,
  ManualArmResult,
  MapPoint,
  MissionReport,
  MissionSnapshot,
  MovementCommandRequest,
  MovementCommandResult,
  MovementControllerState,
  MovementTarget,
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
import KeyboardShortcutsOverlay from "./components/KeyboardShortcutsOverlay.vue";
import ManualArmPanel from "./components/ManualArmPanel.vue";
import MissionHeader from "./components/MissionHeader.vue";
import ObjectPickupPanel from "./components/ObjectPickupPanel.vue";
import RiskMap from "./components/RiskMap.vue";
import RobotActivationPanel from "./components/RobotActivationPanel.vue";
import RobotFleetPanel from "./components/RobotFleetPanel.vue";
import SafetyControls from "./components/SafetyControls.vue";
import ScoutPathPlanner from "./components/ScoutPathPlanner.vue";
import { useKeyboardShortcuts } from "./useKeyboardShortcuts";

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
const movementCommandResult = ref<MovementCommandResult | null>(null);
const commandPaletteRef = ref<InstanceType<typeof CommandPalette> | null>(null);
const scoutPathPlannerRef = ref<InstanceType<typeof ScoutPathPlanner> | null>(null);
const shortcutHelpOpen = ref(false);
const lastShortcut = ref<string | null>(null);
const keyboardDriveEnabled = ref(false);
const keyboardMovementConfig = ref({
  enabled: false,
  robotId: "go2",
  movementTarget: "virtual" as MovementTarget,
  distanceM: 0.25,
  angleDegrees: 10,
});
const busy = ref(false);
const error = ref<string | null>(null);
let socket: WebSocket | null = null;

const missionState = computed(() => snapshot.value?.mission?.state ?? report.value?.state ?? "IDLE");
const runtimeMode = computed(() => runtimeStatus.value?.runtime_mode ?? "mock");
const dryRun = computed(() => runtimeStatus.value?.dry_run ?? true);
const robotMovementTarget = computed<MovementTarget>(
  () =>
    runtimeStatus.value?.robot_movement_target ??
    (runtimeMode.value === "live" && !dryRun.value ? "physical" : "virtual"),
);
const cameraSource = computed<CameraSource>(
  () =>
    runtimeStatus.value?.camera_source ??
    (runtimeMode.value === "live" && !dryRun.value ? "robot" : "pc"),
);
const liveAdapterReady = computed(() => runtimeStatus.value?.live_adapter_ready ?? false);
const runtimeNote = computed(() => runtimeStatus.value?.note ?? "Runtime status unavailable.");
const observations = computed(() => report.value?.observations ?? []);
const latestObservation = computed(() => observations.value.at(-1) ?? null);
const finding = computed(() => report.value?.finding ?? null);
const so101 = computed(() => robots.value.find((robot) => robot.robot_id === "so101") ?? null);
const movementController = computed<MovementControllerState>(
  () =>
    snapshot.value?.movement_controller ?? {
      state: "IDLE",
      robot_id: "go2",
      last_plan: null,
      last_result: null,
      reason: "Movement controller idle.",
      updated_at: new Date().toISOString(),
    },
);

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

async function runGo2MovementCommand(command: MovementCommandRequest) {
  busy.value = true;
  error.value = null;
  try {
    movementCommandResult.value = await sendGo2MovementCommand(command);
    baseMovementResult.value = movementCommandResult.value.result;
    await refresh();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Unknown error";
  } finally {
    busy.value = false;
  }
}

async function runRobotStop(robotId: string) {
  error.value = null;
  lastShortcut.value = `Stop ${robotId}`;
  try {
    robots.value = await stopRobot(robotId);
    await refresh();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Unknown error";
  }
}

function updateKeyboardMovementConfig(config: {
  enabled: boolean;
  robotId: string;
  movementTarget: MovementTarget;
  distanceM: number;
  angleDegrees: number;
}) {
  keyboardDriveEnabled.value = config.enabled;
  keyboardMovementConfig.value = config;
}

function setKeyboardDriveEnabled(enabled: boolean) {
  keyboardDriveEnabled.value = enabled;
  keyboardMovementConfig.value = {
    ...keyboardMovementConfig.value,
    enabled,
  };
}

function runKeyboardMove(action: BaseMovementAction, label: string) {
  const config = keyboardMovementConfig.value;
  if (busy.value || !config.enabled) {
    return;
  }
  lastShortcut.value = label;
  void runBaseMovement(config.robotId, {
    action,
    movement_target: config.movementTarget,
    operator_id: "keyboard",
    operator_confirmed: true,
    distance_m: config.distanceM,
    angle_degrees: config.angleDegrees,
    reason: `Keyboard shortcut ${label} requested bounded movement.`,
  });
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

function stopFromShortcut(label: string) {
  if (busy.value) {
    return;
  }
  lastShortcut.value = label;
  keyboardMovementConfig.value = {
    ...keyboardMovementConfig.value,
    enabled: false,
  };
  keyboardDriveEnabled.value = false;
  void runAction(stopMission);
}

function holdSo101FromShortcut() {
  if (busy.value || !so101.value) {
    return;
  }
  lastShortcut.value = "H";
  void runManualArmTakeover(so101.value.robot_id, {
    action: "hold_position",
    operator_id: "keyboard",
    operator_confirmed: true,
    reason: "Keyboard shortcut H requested SO-101 hold position.",
  });
}

useKeyboardShortcuts(() => [
  { key: "space", handler: () => stopFromShortcut("Space") },
  {
    key: "escape",
    allowEditableTarget: true,
    handler: () => {
      if (shortcutHelpOpen.value) {
        shortcutHelpOpen.value = false;
      }
      stopFromShortcut("Esc");
    },
  },
  { key: "w", handler: () => runKeyboardMove("move_forward", "W") },
  { key: "arrowup", handler: () => runKeyboardMove("move_forward", "ArrowUp") },
  { key: "s", handler: () => runKeyboardMove("move_backward", "S") },
  { key: "arrowdown", handler: () => runKeyboardMove("move_backward", "ArrowDown") },
  { key: "a", shift: true, handler: () => runKeyboardMove("strafe_left", "Shift+A") },
  { key: "d", shift: true, handler: () => runKeyboardMove("strafe_right", "Shift+D") },
  { key: "a", handler: () => runKeyboardMove("rotate_left", "A") },
  { key: "arrowleft", handler: () => runKeyboardMove("rotate_left", "ArrowLeft") },
  { key: "d", handler: () => runKeyboardMove("rotate_right", "D") },
  { key: "arrowright", handler: () => runKeyboardMove("rotate_right", "ArrowRight") },
  {
    key: "f",
    handler: () => {
      if (!busy.value) {
        lastShortcut.value = "F";
        void runAction(() => startMission("FIELD"));
      }
    },
  },
  {
    key: "k",
    ctrlOrMeta: true,
    allowEditableTarget: true,
    handler: () => {
      lastShortcut.value = "Ctrl/Cmd+K";
      commandPaletteRef.value?.focus();
    },
  },
  {
    key: "enter",
    ctrlOrMeta: true,
    allowEditableTarget: true,
    handler: () => {
      if (commandPaletteRef.value?.hasFocus()) {
        lastShortcut.value = "Ctrl/Cmd+Enter";
        commandPaletteRef.value.submit();
      }
    },
  },
  {
    key: "m",
    handler: () => {
      if (!busy.value && latestObservation.value) {
        lastShortcut.value = "M";
        void markCameraObject("MINE");
      }
    },
  },
  {
    key: "n",
    handler: () => {
      if (!busy.value && latestObservation.value) {
        lastShortcut.value = "N";
        void markCameraObject("NOT_MINE");
      }
    },
  },
  {
    key: "u",
    handler: () => {
      if (!busy.value && latestObservation.value) {
        lastShortcut.value = "U";
        void markCameraObject("UNCERTAIN");
      }
    },
  },
  {
    key: "r",
    handler: () => {
      lastShortcut.value = "R";
      scoutPathPlannerRef.value?.submit();
    },
  },
  {
    key: "c",
    handler: () => {
      if (!keyboardMovementConfig.value.enabled) {
        lastShortcut.value = "C";
        scoutPathPlannerRef.value?.clear();
      }
    },
  },
  { key: "h", handler: holdSo101FromShortcut },
  {
    key: "?",
    handler: () => {
      shortcutHelpOpen.value = !shortcutHelpOpen.value;
    },
  },
]);

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
      :robot-movement-target="robotMovementTarget"
      :camera-source="cameraSource"
      :busy="busy"
      @start="(scenario) => runAction(() => startMission(scenario))"
      @stop="() => runAction(stopMission)"
      @runtime-change="(command) => runRuntimeChange(command)"
    />

    <p v-if="error" class="error-banner">{{ error }}</p>
    <p class="shortcut-status">
      <span v-if="lastShortcut">Last shortcut: <kbd>{{ lastShortcut }}</kbd></span>
      <span v-else>Keyboard shortcuts available</span>
      <button type="button" @click="shortcutHelpOpen = true">Keyboard Help <kbd>?</kbd></button>
    </p>

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
          :robot-movement-target="robotMovementTarget"
          :camera-source="cameraSource"
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
          :default-movement-target="robotMovementTarget"
          :movement-controller="movementController"
          :busy="busy"
          :keyboard-drive-enabled="keyboardDriveEnabled"
          @update:keyboard-drive-enabled="setKeyboardDriveEnabled"
          @move="(robotId, command) => runBaseMovement(robotId, command)"
          @movement-command="(command) => runGo2MovementCommand(command)"
          @stop-robot="(robotId) => runRobotStop(robotId)"
          @keyboard-config-change="updateKeyboardMovementConfig"
          @stop="() => runAction(stopMission)"
        />
        <p v-if="baseMovementResult" class="subtle">
          Last base move: {{ baseMovementResult.robot_id }} /
          {{ baseMovementResult.action }}
        </p>
        <p v-if="movementCommandResult" class="subtle">
          Go2 movement FSM: {{ movementCommandResult.state }} /
          {{ movementCommandResult.plan.action ?? "rejected" }}
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
        <ScoutPathPlanner
          ref="scoutPathPlannerRef"
          :busy="busy"
          :route="scoutRoute"
          @plan="planScoutRoute"
        />
        <CameraPanel
          :observation="latestObservation"
          :report="report"
          :streams="cameraStreams"
          :runtime-mode="runtimeMode"
          :camera-source="cameraSource"
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
        <CommandPalette
          ref="commandPaletteRef"
          @command="(text, scenario) => runAction(() => sendCommand(text, scenario))"
        />
        <EventTimeline :events="events" />
      </aside>
    </div>
    <KeyboardShortcutsOverlay :open="shortcutHelpOpen" @close="shortcutHelpOpen = false" />
  </main>
</template>
