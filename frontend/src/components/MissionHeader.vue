<script setup lang="ts">
import { computed } from "vue";
import type { RuntimeConfigRequest } from "../types";
import {
  isPhysicalRuntime,
  physicalRuntimePreset,
  simulatedRuntimePreset,
} from "../runtimePresets";

const props = defineProps<{
  state: string;
  runtimeMode: string;
  dryRun: boolean;
  robotMovementTarget: string;
  cameraSource: string;
  busy: boolean;
}>();

const emit = defineEmits<{
  start: [scenario: string];
  stop: [];
  runtimeChange: [command: RuntimeConfigRequest];
}>();

const physicalModeEnabled = computed(() =>
  isPhysicalRuntime({
    runtime_mode: props.runtimeMode as "mock" | "simulation" | "live",
    dry_run: props.dryRun,
    robot_movement_target: props.robotMovementTarget as "virtual" | "physical" | "auto" | "both",
    camera_source: props.cameraSource as "pc" | "robot",
  }),
);

function onPhysicalToggle(event: Event) {
  const physical = (event.target as HTMLInputElement).checked;
  emit("runtimeChange", physical ? physicalRuntimePreset() : simulatedRuntimePreset());
}
</script>

<template>
  <header class="mission-header panel">
    <div>
      <p class="eyebrow">SafeGround AI</p>
      <h1>Robot Orchestration Console</h1>
      <p class="subtle">Bounded autonomy, mock-object triage, human-in-the-loop control.</p>
    </div>
    <div class="header-toolbar">
      <label class="runtime-toggle simulation-switch header-simulation-switch">
        <span>Fisico</span>
        <input
          :checked="physicalModeEnabled"
          type="checkbox"
          :disabled="busy"
          @change="onPhysicalToggle"
        />
        <span class="toggle-track"></span>
        <span class="simulation-switch-label">
          {{ physicalModeEnabled ? "Robot live · camera robot" : "Simulata · PC camera" }}
        </span>
      </label>
      <div class="mission-status">
        <span class="status-pill">{{ state }}</span>
        <span class="mode-pill">{{ runtimeMode }}</span>
        <span v-if="dryRun" class="dry-run">DRY RUN</span>
        <span v-if="physicalModeEnabled" class="mode-pill physical-pill">FISICO</span>
      </div>
      <div class="header-actions">
        <button :disabled="busy" @click="emit('start', 'FIELD')">Start Field Scan</button>
        <button class="danger" :disabled="busy" @click="emit('stop')">Stop All</button>
      </div>
    </div>
  </header>
</template>
