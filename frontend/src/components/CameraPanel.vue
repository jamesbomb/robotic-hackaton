<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { classifyRobotFrame } from "../api";
import type {
  CameraSource,
  CameraStream,
  ClassificationLabel,
  ClassificationResult,
  FrameClassificationResult,
  MissionReport,
  Observation,
  RuntimeMode,
} from "../types";

const props = defineProps<{
  observation: Observation | null;
  report: MissionReport | null;
  streams: CameraStream[];
  runtimeMode: RuntimeMode;
  cameraSource: CameraSource;
}>();

const emit = defineEmits<{
  mark: [label: ClassificationLabel];
}>();

const VLM_PERIOD_MS = 5000;

const pcVideoRef = ref<HTMLVideoElement | null>(null);
const pcCameraStatus = ref("PC camera standby.");
const disabledStreamIds = ref<Set<string>>(new Set());
const failedStreamIds = ref<Set<string>>(new Set());

const snapshotSrc = ref("");
const snapshotLoading = ref(false);
const snapshotError = ref("");
const snapshotCapturedAt = ref<string | null>(null);

const vlmResult = ref<FrameClassificationResult | null>(null);
const vlmLoading = ref(false);
const vlmError = ref("");
const vlmEnabled = ref(true);
const recognitionImageSize = ref({ width: 0, height: 0 });

let pcCameraStream: MediaStream | null = null;
let vlmTimer: number | null = null;
let snapshotObjectUrl: string | null = null;

const focusRobotId = computed(() => props.observation?.robot_id ?? "go2");
const robotStreams = computed(() => (props.cameraSource === "robot" ? props.streams : []));
const disabledStreamCount = computed(() => disabledStreamIds.value.size);
const shouldRunVlm = computed(
  () => props.cameraSource === "robot" && props.runtimeMode !== "mock" && vlmEnabled.value,
);

const activeClassification = computed<ClassificationResult | null>(
  () => vlmResult.value?.classification ?? props.report?.classification ?? null,
);

const vlmFrameSrc = computed(() => {
  if (!vlmResult.value) {
    return "";
  }
  return `data:${vlmResult.value.frame_media_type};base64,${vlmResult.value.frame_base64}`;
});

function clearSnapshotObjectUrl() {
  if (snapshotObjectUrl) {
    URL.revokeObjectURL(snapshotObjectUrl);
    snapshotObjectUrl = null;
  }
}

function bboxStyle(bbox: number[] | null | undefined) {
  const { width, height } = recognitionImageSize.value;
  if (!bbox || bbox.length < 4 || !width || !height) {
    return null;
  }
  const [x1, y1, x2, y2] = bbox;
  return {
    left: `${(x1 / width) * 100}%`,
    top: `${(y1 / height) * 100}%`,
    width: `${((x2 - x1) / width) * 100}%`,
    height: `${((y2 - y1) / height) * 100}%`,
  };
}

function riskClass(label: ClassificationLabel | undefined) {
  if (label === "MINE") return "mine";
  if (label === "NOT_MINE") return "not_mine";
  return "uncertain";
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

async function captureSnapshot() {
  if (props.cameraSource !== "robot" || props.runtimeMode === "mock") {
    snapshotError.value = "Snapshots are available only in robot camera mode.";
    return;
  }

  snapshotLoading.value = true;
  snapshotError.value = "";
  try {
    const response = await fetch(
      `/api/robots/${focusRobotId.value}/latest-frame?t=${Date.now()}`,
    );
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(
        typeof body?.detail === "string"
          ? body.detail
          : `Snapshot request failed (${response.status}).`,
      );
    }
    const blob = await response.blob();
    if (!blob.type.startsWith("image/")) {
      throw new Error("Cyberwave returned a non-image payload.");
    }
    clearSnapshotObjectUrl();
    snapshotObjectUrl = URL.createObjectURL(blob);
    snapshotSrc.value = snapshotObjectUrl;
    snapshotCapturedAt.value = new Date().toLocaleTimeString();
  } catch (caught) {
    snapshotError.value =
      caught instanceof Error ? caught.message : "Snapshot request failed.";
    clearSnapshotObjectUrl();
    snapshotSrc.value = "";
  } finally {
    snapshotLoading.value = false;
  }
}

async function runVlmRecognition() {
  if (!shouldRunVlm.value) {
    return;
  }

  vlmLoading.value = true;
  vlmError.value = "";
  try {
    vlmResult.value = await classifyRobotFrame(focusRobotId.value);
    recognitionImageSize.value = { width: 0, height: 0 };
  } catch (caught) {
    vlmError.value = caught instanceof Error ? caught.message : "VLM request failed.";
  } finally {
    vlmLoading.value = false;
  }
}

function handleRecognitionImageLoad(event: Event) {
  const image = event.target as HTMLImageElement;
  recognitionImageSize.value = {
    width: image.naturalWidth,
    height: image.naturalHeight,
  };
}

async function startPcCamera() {
  if (pcCameraStream) {
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    pcCameraStatus.value = "PC camera not available in this browser.";
    return;
  }
  pcCameraStatus.value = "Requesting PC camera permission.";
  try {
    pcCameraStream = await navigator.mediaDevices.getUserMedia({
      video: true,
      audio: false,
    });
    if (pcVideoRef.value) {
      pcVideoRef.value.srcObject = pcCameraStream;
    }
    pcCameraStatus.value = "PC camera active for simulated mode.";
  } catch (caught) {
    pcCameraStatus.value =
      caught instanceof Error ? `PC camera unavailable: ${caught.message}` : "PC camera unavailable.";
  }
}

function stopPcCamera() {
  pcCameraStream?.getTracks().forEach((track) => track.stop());
  pcCameraStream = null;
  if (pcVideoRef.value) {
    pcVideoRef.value.srcObject = null;
  }
  pcCameraStatus.value = "PC camera standby.";
}

function startVlmTimer() {
  if (vlmTimer !== null) {
    window.clearInterval(vlmTimer);
  }
  if (!shouldRunVlm.value) {
    return;
  }
  void runVlmRecognition();
  vlmTimer = window.setInterval(() => {
    void runVlmRecognition();
  }, VLM_PERIOD_MS);
}

function stopVlmTimer() {
  if (vlmTimer !== null) {
    window.clearInterval(vlmTimer);
    vlmTimer = null;
  }
}

onMounted(() => {
  if (props.cameraSource === "pc") {
    void startPcCamera();
  }
  startVlmTimer();
});

onUnmounted(() => {
  stopPcCamera();
  stopVlmTimer();
  clearSnapshotObjectUrl();
});

watch(
  () => props.cameraSource,
  (cameraSource) => {
    if (cameraSource === "pc") {
      void startPcCamera();
    } else {
      stopPcCamera();
    }
    startVlmTimer();
  },
);
watch(pcVideoRef, (video) => {
  if (video && pcCameraStream) {
    video.srcObject = pcCameraStream;
  }
});
watch([focusRobotId, shouldRunVlm], () => {
  startVlmTimer();
});
watch(
  () => robotStreams.value.map((stream) => stream.twin_id),
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
    <div class="panel-title camera-section-title">
      <span>Live Video</span>
      <small>{{ cameraSource === "pc" ? "PC camera" : "Robot MJPEG streams" }}</small>
    </div>

    <div v-if="cameraSource === 'pc'" class="pc-camera-card live-video-primary">
      <video ref="pcVideoRef" autoplay muted playsinline></video>
      <small>{{ pcCameraStatus }}</small>
    </div>

    <div v-if="robotStreams.length" class="camera-stream-toolbar">
      <span>{{ robotStreams.length - disabledStreamCount }} / {{ robotStreams.length }} streams active</span>
      <button type="button" :disabled="disabledStreamCount === 0" @click="enableAllStreams">
        Enable all
      </button>
    </div>
    <div v-if="robotStreams.length" class="live-stream-grid live-video-primary">
      <article v-for="stream in robotStreams" :key="stream.twin_id" class="live-stream-card">
        <div>
          <strong>{{ stream.robot_id }}</strong>
          <small>{{ stream.twin_id.slice(0, 8) }}</small>
        </div>
        <img
          v-if="isStreamEnabled(stream)"
          :src="stream.browser_url"
          :alt="`${stream.robot_id} live stream`"
          @load="handleStreamLoad(stream)"
          @error="handleStreamError(stream)"
        />
        <div v-else class="live-stream-disabled">Stream disabled in Web UI.</div>
        <small v-if="failedStreamIds.has(stream.twin_id)" class="stream-error">
          Stream not reachable from browser.
        </small>
        <button type="button" @click="toggleStream(stream)">
          {{ isStreamEnabled(stream) ? "Disable stream" : "Enable stream" }}
        </button>
      </article>
    </div>
    <p v-else-if="cameraSource === 'robot'" class="subtle">
      No Cyberwave stream map found. Pair the robot camera first.
    </p>

    <div class="panel-title camera-section-title">
      <span>VLM Recognition</span>
      <small>{{ vlmResult?.model_id ?? "gemini-robotics-er" }}</small>
    </div>
    <div class="recognition-toolbar">
      <label class="inline-check">
        <input v-model="vlmEnabled" type="checkbox" @change="startVlmTimer()" />
        Auto analyze every {{ VLM_PERIOD_MS / 1000 }}s
      </label>
      <button type="button" :disabled="vlmLoading || !shouldRunVlm" @click="runVlmRecognition()">
        {{ vlmLoading ? "Analyzing..." : "Run VLM now" }}
      </button>
    </div>
    <div class="recognition-stage">
      <img
        v-if="vlmFrameSrc"
        class="recognition-frame-image"
        :src="vlmFrameSrc"
        :alt="`${focusRobotId} VLM analyzed frame`"
        @load="handleRecognitionImageLoad"
      />
      <div
        v-if="activeClassification && bboxStyle(activeClassification.bbox)"
        :class="['recognition-bbox', riskClass(activeClassification.label)]"
        :style="bboxStyle(activeClassification.bbox) ?? undefined"
      >
        <span>{{ activeClassification.label }}</span>
      </div>
      <p v-if="!vlmFrameSrc && !vlmLoading" class="subtle">
        {{
          shouldRunVlm
            ? "Waiting for the first VLM analysis on a robot frame."
            : "Enable robot cameras to run the colleague VLM model."
        }}
      </p>
    </div>
    <div v-if="activeClassification" :class="['classification', riskClass(activeClassification.label)]">
      {{ activeClassification.label }}
      <small>{{ Math.round(activeClassification.confidence * 100) }}%</small>
    </div>
    <p v-if="vlmError" class="stream-error">{{ vlmError }}</p>
    <ul v-if="activeClassification?.evidence.length" class="recognition-evidence">
      <li v-for="item in activeClassification.evidence" :key="item">{{ item }}</li>
    </ul>
    <ul v-if="vlmResult?.detections.length" class="recognition-detections">
      <li v-for="(detection, index) in vlmResult.detections" :key="index">
        {{ detection.class ?? "object" }} / {{ detection.risk ?? "unknown" }}
      </li>
    </ul>

    <div class="panel-title camera-section-title">
      <span>Latest Frame</span>
      <small>Static snapshot</small>
    </div>
    <div class="snapshot-toolbar">
      <button
        type="button"
        :disabled="snapshotLoading || cameraSource !== 'robot' || runtimeMode === 'mock'"
        @click="captureSnapshot()"
      >
        {{ snapshotLoading ? "Capturing..." : "Capture snapshot" }}
      </button>
      <span v-if="snapshotCapturedAt" class="subtle">Last capture: {{ snapshotCapturedAt }}</span>
    </div>
    <div class="frame-stage snapshot-stage">
      <img
        v-if="snapshotSrc"
        class="latest-frame-image snapshot-image"
        :src="snapshotSrc"
        :alt="`${focusRobotId} captured snapshot`"
      />
      <p v-else class="subtle">
        {{
          snapshotError ||
            "No snapshot yet. Use Capture snapshot to freeze one Cyberwave frame (not a live video)."
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
