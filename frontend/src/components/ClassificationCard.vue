<script setup lang="ts">
import type { MissionReport } from "../types";

defineProps<{ report: MissionReport | null }>();
</script>

<template>
  <section class="panel">
    <div class="panel-title">
      <span>Decision</span>
      <small>{{ report?.recommendation ?? "waiting" }}</small>
    </div>
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
  </section>
</template>
