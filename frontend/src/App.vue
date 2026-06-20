<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { connectEvents, getSnapshot, sendCommand, startMission, stopMission } from "./api";
import type { EventRecord, MissionReport, MissionSnapshot, RobotStatus } from "./types";
import CameraPanel from "./components/CameraPanel.vue";
import ClassificationCard from "./components/ClassificationCard.vue";
import CommandPalette from "./components/CommandPalette.vue";
import EventTimeline from "./components/EventTimeline.vue";
import MissionHeader from "./components/MissionHeader.vue";
import RiskMap from "./components/RiskMap.vue";
import RobotFleetPanel from "./components/RobotFleetPanel.vue";
import SafetyControls from "./components/SafetyControls.vue";

const snapshot = ref<MissionSnapshot | null>(null);
const report = ref<MissionReport | null>(null);
const robots = ref<RobotStatus[]>([]);
const events = ref<EventRecord[]>([]);
const busy = ref(false);
const error = ref<string | null>(null);
let socket: WebSocket | null = null;

const missionState = computed(() => report.value?.state ?? snapshot.value?.mission?.state ?? "IDLE");
const runtimeMode = computed(() => snapshot.value?.mission?.runtime_mode ?? "mock");
const dryRun = computed(() => snapshot.value?.mission?.dry_run ?? true);
const observations = computed(() => report.value?.observations ?? []);
const latestObservation = computed(() => observations.value.at(-1) ?? null);
const finding = computed(() => report.value?.finding ?? null);

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
