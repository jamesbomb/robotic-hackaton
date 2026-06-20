<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import {
  connectEvents,
  getSnapshot,
  sendBaseMovementCommand,
  sendCommand,
  sendManualArmCommand,
  startMission,
  stopMission,
} from "./api";
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
import BaseMovementPanel from "./components/BaseMovementPanel.vue";
import CameraPanel from "./components/CameraPanel.vue";
import ClassificationCard from "./components/ClassificationCard.vue";
import CommandPalette from "./components/CommandPalette.vue";
import EventTimeline from "./components/EventTimeline.vue";
import ManualArmPanel from "./components/ManualArmPanel.vue";
import MissionHeader from "./components/MissionHeader.vue";
import RiskMap from "./components/RiskMap.vue";
import RobotFleetPanel from "./components/RobotFleetPanel.vue";
import SafetyControls from "./components/SafetyControls.vue";

const snapshot = ref<MissionSnapshot | null>(null);
const report = ref<MissionReport | null>(null);
const robots = ref<RobotStatus[]>([]);
const events = ref<EventRecord[]>([]);
const manualArmResult = ref<ManualArmResult | null>(null);
const baseMovementResult = ref<BaseMovementResult | null>(null);
const busy = ref(false);
const error = ref<string | null>(null);
let socket: WebSocket | null = null;

const missionState = computed(() => snapshot.value?.mission?.state ?? report.value?.state ?? "IDLE");
const runtimeMode = computed(() => snapshot.value?.mission?.runtime_mode ?? "mock");
const dryRun = computed(() => snapshot.value?.mission?.dry_run ?? true);
const observations = computed(() => report.value?.observations ?? []);
const latestObservation = computed(() => observations.value.at(-1) ?? null);
const finding = computed(() => report.value?.finding ?? null);
const so101 = computed(() => robots.value.find((robot) => robot.robot_id === "so101") ?? null);

async function refresh() {
  snapshot.value = await getSnapshot();
  report.value = snapshot.value.report;
  robots.value = snapshot.value.robots;
  events.value = snapshot.value.events;
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
        <SafetyControls :dry-run="dryRun" :runtime-mode="runtimeMode" @stop="() => runAction(stopMission)" />
        <BaseMovementPanel
          :robots="robots"
          :busy="busy"
          @move="(robotId, command) => runBaseMovement(robotId, command)"
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
        <CameraPanel :observation="latestObservation" />
      </section>

      <aside class="right-rail">
        <ClassificationCard :report="report" />
        <CommandPalette @command="(text, scenario) => runAction(() => sendCommand(text, scenario))" />
        <EventTimeline :events="events" />
      </aside>
    </div>
  </main>
</template>
