<script setup lang="ts">
import type { CameraStream, ClassificationLabel, Observation } from "../types";

defineProps<{
  observation: Observation | null;
  streams: CameraStream[];
}>();

const emit = defineEmits<{
  mark: [label: ClassificationLabel];
}>();
</script>

<template>
  <section class="panel camera-panel">
    <div class="panel-title">
      <span>Latest Frame</span>
      <small>{{ observation?.sensor_id ?? "no feed" }}</small>
    </div>
    <div v-if="streams.length" class="live-stream-grid">
      <article v-for="stream in streams" :key="stream.twin_id" class="live-stream-card">
        <div>
          <strong>{{ stream.robot_id }}</strong>
          <small>{{ stream.twin_id.slice(0, 8) }}</small>
        </div>
        <img :src="stream.browser_url" :alt="`${stream.robot_id} camera stream`" />
        <small>{{ stream.browser_url }}</small>
      </article>
    </div>
    <p v-else class="subtle">
      No Cyberwave camera stream map found. Run `cyberwave pair` / camera setup first.
    </p>
    <div class="frame-stage">
      <div v-if="observation" class="bbox">
        <span>{{ observation.classification.label }}</span>
      </div>
      <p v-else>No frame captured yet.</p>
    </div>
    <div class="camera-mark-controls">
      <span>Mark object</span>
      <button :disabled="!observation" class="mark-mine" @click="emit('mark', 'MINE')">Mine</button>
      <button :disabled="!observation" class="mark-not-mine" @click="emit('mark', 'NOT_MINE')">
        Not mine
      </button>
      <button :disabled="!observation" class="mark-uncertain" @click="emit('mark', 'UNCERTAIN')">
        Uncertain
      </button>
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
