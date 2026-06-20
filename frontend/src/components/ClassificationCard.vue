<script setup lang="ts">
import CollapsiblePanel from "./CollapsiblePanel.vue";
import type { MissionReport } from "../types";

defineProps<{ report: MissionReport | null }>();
</script>

<template>
  <CollapsiblePanel title="Decision" :meta="report?.recommendation ?? 'waiting'">
    <template v-if="report?.classification">
      <div :class="['classification', report.classification.label.toLowerCase()]">
        {{ report.classification.label }}
      </div>
      <div class="confidence">
        <span>Confidence</span>
        <strong>{{ Math.round(report.classification.confidence * 100) }}%</strong>
      </div>
      <p>{{ report.summary }}</p>
      <ul>
        <li v-for="item in report.classification.evidence" :key="item">{{ item }}</li>
      </ul>
    </template>
    <p v-else class="subtle">No active classification. Start a mission or send a command.</p>
  </CollapsiblePanel>
</template>
