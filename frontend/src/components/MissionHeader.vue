<script setup lang="ts">
defineProps<{
  state: string;
  runtimeMode: string;
  dryRun: boolean;
  busy: boolean;
}>();

const emit = defineEmits<{
  start: [scenario: string];
  stop: [];
}>();
</script>

<template>
  <header class="mission-header panel">
    <div>
      <p class="eyebrow">SafeGround AI</p>
      <h1>Robot Orchestration Console</h1>
      <p class="subtle">Bounded autonomy, mock-object triage, human-in-the-loop control.</p>
    </div>
    <div class="mission-status">
      <span class="status-pill">{{ state }}</span>
      <span class="mode-pill">{{ runtimeMode }}</span>
      <span v-if="dryRun" class="dry-run">DRY RUN</span>
    </div>
    <div class="header-actions">
      <button :disabled="busy" @click="emit('start', 'FIELD')">Start Field Scan</button>
      <button class="danger" :disabled="busy" @click="emit('stop')">Stop All</button>
    </div>
  </header>
</template>
