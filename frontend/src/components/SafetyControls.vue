<script setup lang="ts">
import { ref, watch } from "vue";
import type { RuntimeConfigRequest, RuntimeMode } from "../types";
import CollapsiblePanel from "./CollapsiblePanel.vue";

const props = defineProps<{
  dryRun: boolean;
  runtimeMode: RuntimeMode;
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

watch(
  () => [props.runtimeMode, props.dryRun] as const,
  ([runtimeMode, dryRun]) => {
    selectedRuntimeMode.value = runtimeMode;
    selectedDryRun.value = dryRun;
  },
);

function updateRuntime() {
  emit("runtimeChange", {
    runtime_mode: selectedRuntimeMode.value,
    dry_run: selectedDryRun.value,
    operator_confirmed: true,
    reason: `Operator selected ${selectedRuntimeMode.value} runtime from the dashboard.`,
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
      <p class="subtle">{{ runtimeNote }}</p>
    </div>

    <button class="danger full" @click="emit('stop')">Emergency Stop All</button>
  </CollapsiblePanel>
</template>
