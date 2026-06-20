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
const latestFrameFailed = ref(false);
const disabledStreamIds = ref<Set<string>>(new Set());
const failedStreamIds = ref<Set<string>>(new Set());
let refreshTimer: number | null = null;

const latestFrameRobotId = computed(() => props.observation?.robot_id ?? "go2");
const shouldPollLatestFrame = computed(() => props.runtimeMode !== "mock");
const disabledStreamCount = computed(() => disabledStreamIds.value.size);

function refreshLatestFrame() {
  if (!shouldPollLatestFrame.value) {
    latestFrameSrc.value = "";
    latestFrameAvailable.value = false;
    return;
  }
  latestFrameFailed.value = false;
  latestFrameSrc.value = `/api/robots/${latestFrameRobotId.value}/latest-frame?t=${Date.now()}`;
}

function handleLatestFrameLoad() {
  latestFrameAvailable.value = true;
  latestFrameFailed.value = false;
}

function handleLatestFrameError() {
  latestFrameAvailable.value = false;
  latestFrameFailed.value = true;
}

function isStreamEnabled(stream: CameraStream) {
  return !disabledStreamIds.value.has(stream.twin_id);
}

function toggleStream(stream: CameraStream) {
  const next = new Set(disabledStreamIds.value);
  if (next.has(stream.twin_id)) {
    next.delete(stream.twin_id);
  } else {
    next.add(stream.twin_id);
  }
  disabledStreamIds.value = next;
}

function enableAllStreams() {
  disabledStreamIds.value = new Set();
}

function handleStreamLoad(stream: CameraStream) {
  const next = new Set(failedStreamIds.value);
  next.delete(stream.twin_id);
  failedStreamIds.value = next;
}

function handleStreamError(stream: CameraStream) {
  failedStreamIds.value = new Set([...failedStreamIds.value, stream.twin_id]);
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
watch(
  () => props.streams.map((stream) => stream.twin_id),
  (streamIds) => {
    const current = new Set(streamIds);
    disabledStreamIds.value = new Set(
      [...disabledStreamIds.value].filter((streamId) => current.has(streamId)),
    );
    failedStreamIds.value = new Set(
      [...failedStreamIds.value].filter((streamId) => current.has(streamId)),
    );
  },
);
</script>

<template>
  <section class="panel camera-panel">
    <div class="panel-title">
      <span>Latest Frame</span>
      <small>{{ observation?.sensor_id ?? "no feed" }}</small>
    </div>
    <div v-if="streams.length" class="camera-stream-toolbar">
      <span>{{ streams.length - disabledStreamCount }} / {{ streams.length }} cameras active</span>
      <button type="button" :disabled="disabledStreamCount === 0" @click="enableAllStreams">
        Enable all
      </button>
    </div>
    <div v-if="streams.length" class="live-stream-grid">
      <article v-for="stream in streams" :key="stream.twin_id" class="live-stream-card">
        <div>
          <strong>{{ stream.robot_id }}</strong>
          <small>{{ stream.twin_id.slice(0, 8) }}</small>
        </div>
        <img
          v-if="isStreamEnabled(stream)"
          :src="stream.browser_url"
          :alt="`${stream.robot_id} camera stream`"
          @load="handleStreamLoad(stream)"
          @error="handleStreamError(stream)"
        />
        <div v-else class="live-stream-disabled">
          Camera disabled in Web UI.
        </div>
        <small>{{ stream.browser_url }}</small>
        <small v-if="failedStreamIds.has(stream.twin_id)" class="stream-error">
          Stream not reachable from browser. Check local port and Cyberwave camera process.
        </small>
        <button type="button" @click="toggleStream(stream)">
          {{ isStreamEnabled(stream) ? "Disable camera" : "Enable camera" }}
        </button>
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
          latestFrameFailed
            ? "Latest frame unavailable. Check CYBERWAVE_API_KEY / CYBERWAVE_ENVIRONMENT and camera frame support."
            : shouldPollLatestFrame
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
