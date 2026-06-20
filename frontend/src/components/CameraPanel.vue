<script setup lang="ts">
import type { Observation } from "../types";

defineProps<{ observation: Observation | null }>();
</script>

<template>
  <section class="panel camera-panel">
    <div class="panel-title">
      <span>Latest Frame</span>
      <small>{{ observation?.sensor_id ?? "no feed" }}</small>
    </div>
    <div class="frame-stage">
      <div v-if="observation" class="bbox">
        <span>{{ observation.classification.label }}</span>
      </div>
      <p v-else>No frame captured yet.</p>
    </div>
    <dl v-if="observation" class="data-list">
      <div>
        <dt>Frame</dt>
        <dd>{{ observation.frame.frame_id }}</dd>
      </div>
      <div>
        <dt>Source</dt>
        <dd>{{ observation.frame.source }}</dd>
      </div>
      <div>
        <dt>BBox</dt>
        <dd>{{ observation.classification.bbox?.join(", ") ?? "n/a" }}</dd>
      </div>
    </dl>
  </section>
</template>
