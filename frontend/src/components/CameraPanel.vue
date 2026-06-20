<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { classifyImage, classifyRobotFrame } from "../api";
import type {
  CameraSource,
  CameraStream,
  ClassificationLabel,
  FrameClassificationResult,
  MissionReport,
  Observation,
  RuntimeMode,
} from "../types";

interface VlmDetection {
  class?: string;
  risk?: string;
  confidence?: number;
  bbox?: number[];
}

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
const SOURCE_SWITCH_DELAY_MS = 800;

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
const vlmSourceLabel = ref("starting");

let pcCameraStream: MediaStream | null = null;
let vlmTimer: number | null = null;
let vlmSession = 0;
let snapshotObjectUrl: string | null = null;

const focusRobotId = computed(() => props.observation?.robot_id ?? "go2");
const robotStreams = computed(() => (props.cameraSource === "robot" ? props.streams : []));
const disabledStreamCount = computed(() => disabledStreamIds.value.size);

const liveDetections = computed(() => {
  const detections = vlmResult.value?.detections ?? [];
  return detections
    .map((item) => item as VlmDetection)
    .filter((item) => Array.isArray(item.bbox) && item.bbox.length >= 4);
});

const detectionCounts = computed(() => {
  const counts = { SAFE: 0, DANGER: 0, AVOID: 0 };
  for (const detection of liveDetections.value) {
    const risk = detection.risk?.toUpperCase();
    if (risk === "SAFE" || risk === "DANGER" || risk === "AVOID") {
      counts[risk] += 1;
    }
  }
  return counts;
});

const vlmStatusText = computed(() => {
  if (vlmLoading.value) {
    return `Analyzing ${vlmSourceLabel.value} frame...`;
  }
  if (vlmError.value) {
    return vlmError.value;
  }
  return `Active on ${vlmSourceLabel.value} · every ${VLM_PERIOD_MS / 1000}s`;
});

function clearSnapshotObjectUrl() {
  if (snapshotObjectUrl) {
    URL.revokeObjectURL(snapshotObjectUrl);
    snapshotObjectUrl = null;
  }
}

function detectionOverlayStyle(bbox: number[] | undefined) {
  if (!bbox || bbox.length < 4) {
    return null;
  }
  const [a, b, c, d] = bbox;
  if (Math.max(...bbox) <= 1) {
    return {
      left: `${(a * 100).toFixed(2)}%`,
      top: `${(b * 100).toFixed(2)}%`,
      width: `${(c * 100).toFixed(2)}%`,
      height: `${(d * 100).toFixed(2)}%`,
    };
  }
  return null;
}

function riskClassFromDetection(detection: VlmDetection) {
  if (detection.risk === "DANGER") return "mine";
  if (detection.risk === "SAFE") return "not_mine";
  return "uncertain";
}

function detectionLabel(detection: VlmDetection) {
  const confidence = Math.round((detection.confidence ?? 0) * 100);
  return `${detection.risk ?? "?"} ${confidence}% · ${detection.class ?? "object"}`;
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

function capturePcFrameBase64(): string | null {
  const video = pcVideoRef.value;
  if (!video || video.videoWidth === 0 || video.videoHeight === 0) {
    return null;
  }
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const context = canvas.getContext("2d");
  if (!context) {
    return null;
  }
  context.drawImage(video, 0, 0, canvas.width, canvas.height);
  const dataUrl = canvas.toDataURL("image/jpeg", 0.88);
  const [, payload] = dataUrl.split(",", 2);
  return payload ?? null;
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

function stopVlmLoop() {
  vlmSession += 1;
  if (vlmTimer !== null) {
    window.clearTimeout(vlmTimer);
    vlmTimer = null;
  }
}

function scheduleVlmTick(session: number, delayMs = 0) {
  if (session !== vlmSession) {
    return;
  }
  if (vlmTimer !== null) {
    window.clearTimeout(vlmTimer);
  }
  vlmTimer = window.setTimeout(() => {
    void runVlmRecognition(session);
  }, delayMs);
}

async function runVlmRecognition(session: number) {
  if (session !== vlmSession) {
    return;
  }

  vlmLoading.value = true;
  vlmError.value = "";
  try {
    if (props.cameraSource === "pc") {
      vlmSourceLabel.value = "PC webcam";
      const imageBase64 = capturePcFrameBase64();
      if (!imageBase64) {
        throw new Error("PC camera frame is not ready yet.");
      }
      const result = await classifyImage(imageBase64);
      if (session !== vlmSession) {
        return;
      }
      vlmResult.value = result;
    } else {
      vlmSourceLabel.value = `${focusRobotId.value} robot camera`;
      const result = await classifyRobotFrame(focusRobotId.value);
      if (session !== vlmSession) {
        return;
      }
      vlmResult.value = result;
    }
  } catch (caught) {
    if (session !== vlmSession) {
      return;
    }
    vlmError.value = caught instanceof Error ? caught.message : "VLM request failed.";
  } finally {
    if (session === vlmSession) {
      vlmLoading.value = false;
      scheduleVlmTick(session, VLM_PERIOD_MS);
    }
  }
}

function restartVlmRecognition(reason = "source change") {
  stopVlmLoop();
  vlmResult.value = null;
  vlmError.value = "";
  vlmLoading.value = false;
  vlmSourceLabel.value =
    props.cameraSource === "pc"
      ? "PC webcam"
      : `${focusRobotId.value} robot camera`;
  const session = vlmSession;
  const delayMs = reason === "source change" ? SOURCE_SWITCH_DELAY_MS : 0;
  scheduleVlmTick(session, delayMs);
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
    pcCameraStatus.value = "PC camera active.";
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

async function applyCameraSource(cameraSource: CameraSource) {
  if (cameraSource === "pc") {
    await startPcCamera();
  } else {
    stopPcCamera();
  }
  restartVlmRecognition("source change");
}

onMounted(() => {
  void applyCameraSource(props.cameraSource);
});

onUnmounted(() => {
  stopVlmLoop();
  stopPcCamera();
  clearSnapshotObjectUrl();
});

watch(
  () => [props.cameraSource, props.runtimeMode] as const,
  (current, previous) => {
    if (!previous) {
      return;
    }
    const [cameraSource] = current;
    const [previousCameraSource] = previous;
    if (cameraSource !== previousCameraSource) {
      void applyCameraSource(cameraSource);
      return;
    }
    restartVlmRecognition("runtime change");
  },
);
watch(pcVideoRef, (video) => {
  if (video && pcCameraStream) {
    video.srcObject = pcCameraStream;
  }
});
watch(focusRobotId, () => {
  if (props.cameraSource === "robot") {
    restartVlmRecognition("robot focus change");
  }
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
      <span>Live Video + VLM</span>
      <small>{{ vlmResult?.model_id ?? "gemini-robotics-er" }}</small>
    </div>

    <div class="recognition-toolbar">
      <div class="vlm-hud">
        <span class="hud-safe">SAFE {{ detectionCounts.SAFE }}</span>
        <span class="hud-danger">DANGER {{ detectionCounts.DANGER }}</span>
        <span class="hud-avoid">AVOID {{ detectionCounts.AVOID }}</span>
      </div>
      <span :class="['vlm-status', { 'vlm-status-loading': vlmLoading, 'vlm-status-error': vlmError }]">
        {{ vlmStatusText }}
      </span>
    </div>
    <p v-if="vlmResult && !vlmResult.valid && !vlmError" class="subtle">
      {{ vlmResult.validation_errors?.join(" · ") || "VLM returned no valid detections." }}
    </p>

    <div v-if="cameraSource === 'pc'" class="live-feed-stage live-video-primary">
      <video ref="pcVideoRef" autoplay muted playsinline></video>
      <div
        v-for="(detection, index) in liveDetections"
        :key="`pc-${index}`"
        :class="['live-detection-box', riskClassFromDetection(detection)]"
        :style="detectionOverlayStyle(detection.bbox) ?? undefined"
      >
        <span>{{ detectionLabel(detection) }}</span>
      </div>
      <small class="live-feed-caption">{{ pcCameraStatus }}</small>
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
        <div v-if="isStreamEnabled(stream)" class="live-feed-stage">
          <img
            :src="stream.browser_url"
            :alt="`${stream.robot_id} live stream`"
            @load="handleStreamLoad(stream)"
            @error="handleStreamError(stream)"
          />
          <template v-if="stream.robot_id === focusRobotId">
            <div
              v-for="(detection, index) in liveDetections"
              :key="`${stream.twin_id}-${index}`"
              :class="['live-detection-box', riskClassFromDetection(detection)]"
              :style="detectionOverlayStyle(detection.bbox) ?? undefined"
            >
              <span>{{ detectionLabel(detection) }}</span>
            </div>
          </template>
        </div>
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

    <div v-if="vlmResult?.classification" :class="['classification', riskClassFromDetection({ risk: vlmResult.classification.label === 'MINE' ? 'DANGER' : vlmResult.classification.label === 'NOT_MINE' ? 'SAFE' : 'AVOID' })]">
      Mission label: {{ vlmResult.classification.label }}
      <small>{{ Math.round(vlmResult.classification.confidence * 100) }}%</small>
    </div>

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
            "No snapshot yet. Capture freezes one Cyberwave frame (not the live feed)."
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
