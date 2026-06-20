<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { CameraSource, MovementTarget, RuntimeConfigRequest, RuntimeMode } from "../types";
import {
  isPhysicalRuntime,
  physicalRuntimePreset,
  simulatedRuntimePreset,
  syncRoutingWithRuntime,
} from "../runtimePresets";
import CollapsiblePanel from "./CollapsiblePanel.vue";

const props = defineProps<{
  dryRun: boolean;
  runtimeMode: RuntimeMode;
  robotMovementTarget: MovementTarget;
  cameraSource: CameraSource;
  liveAdapterReady: boolean;
  runtimeNote: string;
  busy: boolean;
}>();
const emit = defineEmits<{
  stop: [];
  runtimeChange: [command: RuntimeConfigRequest];
}>();

const selectedRuntimeMode = ref<RuntimeMode>(props.runtimeMode);
const selectedDryRun = ref(props.dryRun);
const selectedRobotMovementTarget = ref<MovementTarget>(props.robotMovementTarget);
const selectedCameraSource = ref<CameraSource>(props.cameraSource);

watch(
  () =>
    [
      props.runtimeMode,
      props.dryRun,
      props.robotMovementTarget,
      props.cameraSource,
    ] as const,
  ([runtimeMode, dryRun, robotMovementTarget, cameraSource]) => {
    selectedRuntimeMode.value = runtimeMode;
    selectedDryRun.value = dryRun;
    selectedRobotMovementTarget.value = robotMovementTarget;
    selectedCameraSource.value = cameraSource;
  },
);

watch([selectedRuntimeMode, selectedDryRun], ([runtimeMode, dryRun]) => {
  const synced = syncRoutingWithRuntime(runtimeMode, dryRun, {
    runtime_mode: selectedRuntimeMode.value,
    dry_run: selectedDryRun.value,
    robot_movement_target: selectedRobotMovementTarget.value,
    camera_source: selectedCameraSource.value,
  });
  selectedRuntimeMode.value = synced.runtime_mode;
  selectedDryRun.value = synced.dry_run;
  selectedRobotMovementTarget.value = synced.robot_movement_target;
  selectedCameraSource.value = synced.camera_source;
});

function applyPhysicalPreset() {
  emit("runtimeChange", physicalRuntimePreset("Operator selected physical preset from Safety panel."));
}

function applySimulatedPreset() {
  emit("runtimeChange", simulatedRuntimePreset("Operator selected simulated preset from Safety panel."));
}

function updateRuntime() {
  submitRuntime("Operator selected runtime settings from the dashboard.");
}

function submitRuntime(reason: string) {
  emit("runtimeChange", {
    runtime_mode: selectedRuntimeMode.value,
    dry_run: selectedDryRun.value,
    robot_movement_target: selectedRobotMovementTarget.value,
    camera_source: selectedCameraSource.value,
    operator_confirmed: true,
    reason,
  });
}

const physicalActive = computed(() =>
  isPhysicalRuntime({
    runtime_mode: props.runtimeMode,
    dry_run: props.dryRun,
    robot_movement_target: props.robotMovementTarget,
    camera_source: props.cameraSource,
  }),
);
</script>

<template>
  <CollapsiblePanel title="Safety" :meta="runtimeMode" panel-class="safety-panel">
    <p>
      Physical movement remains blocked by default. Use the header switch or the presets below
      before arming robots or sending live motion.
    </p>

    <div class="runtime-preset-actions">
      <button type="button" :disabled="busy || physicalActive" @click="applyPhysicalPreset">
        Passa a fisico
      </button>
      <button type="button" :disabled="busy || !physicalActive" @click="applySimulatedPreset">
        Torna a simulata
      </button>
    </div>

    <div class="safety-grid">
      <span>Dry run</span>
      <strong>{{ dryRun ? "enabled" : "disabled" }}</strong>
      <span>Live adapter</span>
      <strong>{{ liveAdapterReady ? "ready" : "not wired" }}</strong>
      <span>Robot target</span>
      <strong>{{ robotMovementTarget }}</strong>
      <span>Camera</span>
      <strong>{{ cameraSource }}</strong>
      <span>Contact with target</span>
      <strong>blocked</strong>
      <span>Stop path</span>
      <strong>available</strong>
    </div>

    <div class="runtime-controls">
      <label>
        Runtime
        <select v-model="selectedRuntimeMode" :disabled="busy" @change="updateRuntime">
          <option value="mock">Mock</option>
          <option value="simulation">Simulation</option>
          <option value="live">Live</option>
        </select>
      </label>
      <label class="inline-check">
        <input v-model="selectedDryRun" type="checkbox" :disabled="busy" @change="updateRuntime" />
        Keep dry-run enabled
      </label>
      <div class="runtime-routing-grid">
        <label>
          Robot target
          <select v-model="selectedRobotMovementTarget" :disabled="busy" @change="updateRuntime">
            <option value="virtual">Virtual dashboard twin</option>
            <option value="physical">Physical robot</option>
          </select>
        </label>
        <label>
          Camera source
          <select v-model="selectedCameraSource" :disabled="busy" @change="updateRuntime">
            <option value="pc">PC camera</option>
            <option value="robot">Robot cameras</option>
          </select>
        </label>
      </div>
      <p class="subtle">{{ runtimeNote }}</p>
    </div>

    <button class="danger full" @click="emit('stop')">Emergency Stop All</button>
  </CollapsiblePanel>
</template>
