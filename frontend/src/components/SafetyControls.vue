<script setup lang="ts">
import { ref, watch } from "vue";
import type { CameraSource, MovementTarget, RuntimeConfigRequest, RuntimeMode } from "../types";
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
</script>

<template>
  <CollapsiblePanel title="Safety" :meta="runtimeMode" panel-class="safety-panel">
    <p>
      Physical movement remains blocked by default. The system only emits allow-listed
      actions and requires human takeover for live robot motion.
    </p>
    <div class="safety-grid">
      <span>Dry run</span>
      <strong>{{ dryRun ? "enabled" : "disabled" }}</strong>
      <span>Live adapter</span>
      <strong>{{ liveAdapterReady ? "ready" : "not wired" }}</strong>
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
