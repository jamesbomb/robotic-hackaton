<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import type { CameraStream, ClassificationLabel, Observation, RuntimeMode } from "../types";

const props = defineProps<{
  observation: Observation | null;
  streams: CameraStream[];
  runtimeMode: RuntimeMode;
}>();

const emit = defineEmits<{
  mark: [label: ClassificationLabel];
}>();

const latestFrameSrc = ref("");
const latestFrameAvailable = ref(false);
let refreshTimer: number | null = null;

const latestFrameRobotId = computed(() => props.observation?.robot_id ?? "go2");
const shouldPollLatestFrame = computed(() => props.runtimeMode !== "mock");

function refreshLatestFrame() {
  if (!shouldPollLatestFrame.value) {
    latestFrameSrc.value = "";
    latestFrameAvailable.value = false;
    return;
  }
  latestFrameSrc.value = `/api/robots/${latestFrameRobotId.value}/latest-frame?t=${Date.now()}`;
}

function handleLatestFrameLoad() {
  latestFrameAvailable.value = true;
}

function handleLatestFrameError() {
  latestFrameAvailable.value = false;
}

onMounted(() => {
  refreshLatestFrame();
  refreshTimer = window.setInterval(refreshLatestFrame, 2000);
});

onUnmounted(() => {
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer);
  }
});

watch([latestFrameRobotId, shouldPollLatestFrame], refreshLatestFrame);
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
      <img
        v-if="latestFrameSrc"
        v-show="latestFrameAvailable"
        class="latest-frame-image"
        :src="latestFrameSrc"
        :alt="`${latestFrameRobotId} latest Cyberwave frame`"
        @load="handleLatestFrameLoad"
        @error="handleLatestFrameError"
      />
      <div v-if="observation" class="bbox">
        <span>{{ observation.classification.label }}</span>
      </div>
      <p v-if="!latestFrameAvailable && !observation" class="subtle">
        {{
          shouldPollLatestFrame
            ? "Waiting for Cyberwave latest frame."
            : "Switch to simulation/live to read latest Cyberwave frames."
        }}
      </p>
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
