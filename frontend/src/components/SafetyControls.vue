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

const liveEnabled = ref(props.runtimeMode === "live" && !props.dryRun);

watch(
  () => [props.runtimeMode, props.dryRun] as const,
  ([runtimeMode, dryRun]) => {
    liveEnabled.value = runtimeMode === "live" && !dryRun;
  },
);

function toggleLive() {
  emit("runtimeChange", {
    runtime_mode: liveEnabled.value ? "live" : "mock",
    dry_run: !liveEnabled.value,
    operator_confirmed: true,
    reason: liveEnabled.value
      ? "Operator enabled live non-dry-run from the dashboard toggle."
      : "Operator returned the dashboard to mock dry-run mode.",
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
      <label class="runtime-toggle">
        <span>Dry run</span>
        <input
          v-model="liveEnabled"
          type="checkbox"
          role="switch"
          :disabled="busy"
          @change="toggleLive"
        />
        <span class="toggle-track" aria-hidden="true"></span>
        <span>Live</span>
      </label>
      <p class="subtle">{{ runtimeNote }}</p>
    </div>

    <button class="danger full" @click="emit('stop')">Emergency Stop All</button>
  </CollapsiblePanel>
</template>
