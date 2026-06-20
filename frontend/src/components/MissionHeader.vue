<script setup lang="ts">
import { ref, watch } from "vue";
import type { CameraSource, MovementTarget, RuntimeConfigRequest, RuntimeMode } from "../types";

const props = defineProps<{
  state: string;
  runtimeMode: RuntimeMode;
  dryRun: boolean;
  robotMovementTarget: MovementTarget;
  cameraSource: CameraSource;
  busy: boolean;
}>();

const emit = defineEmits<{
  start: [scenario: string];
  stop: [];
  runtimeChange: [command: RuntimeConfigRequest];
}>();

const simulationEnabled = ref(isSimulatedMode());

watch(
  () =>
    [props.runtimeMode, props.dryRun, props.robotMovementTarget, props.cameraSource] as const,
  ([runtimeMode, dryRun, robotMovementTarget, cameraSource]) => {
    simulationEnabled.value = isSimulatedMode(
      runtimeMode,
      dryRun,
      robotMovementTarget,
      cameraSource,
    );
  },
);

function isSimulatedMode(
  runtimeMode = props.runtimeMode,
  dryRun = props.dryRun,
  robotMovementTarget = props.robotMovementTarget,
  cameraSource = props.cameraSource,
) {
  return (
    runtimeMode !== "live" ||
    dryRun ||
    cameraSource !== "robot" ||
    robotMovementTarget !== "physical"
  );
}

function applySimulationSwitch(enabled: boolean) {
  emit("runtimeChange", {
    runtime_mode: enabled ? "simulation" : "live",
    dry_run: enabled,
    robot_movement_target: enabled ? "virtual" : "physical",
    camera_source: enabled ? "pc" : "robot",
    operator_confirmed: true,
    reason: enabled
      ? "Operator enabled simulated mode: virtual robots and PC camera."
      : "Operator enabled physical mode: physical robots and onboard robot cameras.",
  });
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
        <span>Simulata</span>
        <input
          v-model="simulationEnabled"
          type="checkbox"
          :disabled="busy"
          @change="applySimulationSwitch(simulationEnabled)"
        />
        <span class="toggle-track"></span>
        <span class="simulation-switch-label">
          {{ simulationEnabled ? "Virtuali / PC" : "Fisici / Robot" }}
        </span>
      </label>
      <div class="mission-status">
        <span class="status-pill">{{ state }}</span>
        <span class="mode-pill">{{ runtimeMode }}</span>
        <span v-if="dryRun" class="dry-run">DRY RUN</span>
      </div>
      <div class="header-actions">
        <button :disabled="busy" @click="emit('start', 'FIELD')">Start Field Scan</button>
        <button class="danger" :disabled="busy" @click="emit('stop')">Stop All</button>
      </div>
    </div>
  </header>
</template>
