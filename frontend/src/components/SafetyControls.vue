<script setup lang="ts">
defineProps<{ dryRun: boolean; runtimeMode: string }>();
const emit = defineEmits<{ stop: [] }>();
</script>

<template>
  <section class="panel safety-panel">
    <div class="panel-title">
      <span>Safety</span>
      <small>{{ runtimeMode }}</small>
    </div>
    <p>
      Physical movement remains blocked by default. The system only emits allow-listed
      actions and requires human takeover for live robot motion.
    </p>
    <div class="safety-grid">
      <span>Dry run</span>
      <strong>{{ dryRun ? "enabled" : "disabled" }}</strong>
      <span>Contact with target</span>
      <strong>blocked</strong>
      <span>Stop path</span>
      <strong>available</strong>
    </div>
    <button class="danger full" @click="emit('stop')">Emergency Stop All</button>
  </section>
</template>
