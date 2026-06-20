<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import VideoFeedOverlay, { type FeedDetection } from "./VideoFeedOverlay.vue";
import type {
  CameraSource,
  CameraStream,
  ClassificationLabel,
  FrameClassificationResult,
  MissionReport,
  Observation,
  RiskMapState,
  RuntimeMode,
} from "../types";

const props = defineProps<{
  observation: Observation | null;
  report: MissionReport | null;
  streams: CameraStream[];
  runtimeMode: RuntimeMode;
  cameraSource: CameraSource;
  riskMap: RiskMapState | null;
  visionResult: FrameClassificationResult | null;
  visionStatus: Record<string, unknown> | null;
}>();

const emit = defineEmits<{
  mark: [label: ClassificationLabel];
  "risk-map-update": [riskMap: RiskMapState];
}>();

const LIVE_FRAME_MS = 120;

const disabledStreamIds = ref<Set<string>>(new Set());
const failedStreamIds = ref<Set<string>>(new Set());
const pcFrameSrc = ref("");
const pcCameraStatus = ref("Live vision worker starting...");

const snapshotSrc = ref("");
const snapshotLoading = ref(false);
const snapshotError = ref("");
const snapshotCapturedAt = ref<string | null>(null);

let liveFrameTimer: number | null = null;
let snapshotObjectUrl: string | null = null;

const focusRobotId = computed(() => props.observation?.robot_id ?? "go2");
const robotStreams = computed(() => (props.cameraSource === "robot" ? props.streams : []));
const disabledStreamCount = computed(() => disabledStreamIds.value.size);

const liveDetections = computed(() => {
  const detections = props.visionResult?.detections ?? [];
  return detections
    .map((item) => item as FeedDetection)
    .filter((item) => Array.isArray(item.bbox) && item.bbox.length >= 4);
});

const overlayRiskMap = computed(() => props.riskMap ?? props.visionResult?.risk_map ?? null);

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
  const state = String(props.visionStatus?.vlm_state ?? "starting");
  const source =
    props.cameraSource === "pc"
      ? `PC cam ${String(props.visionStatus?.camera_index ?? 0)}`
      : `${focusRobotId.value} robot camera`;
  const lastError = props.visionStatus?.last_error;
  if (typeof lastError === "string" && lastError.length > 0) {
    return lastError;
  }
  if (state === "analyzing") {
    return `Live vision analyzing ${source}...`;
  }
  if (state === "error") {
    return `Live vision error on ${source}.`;
  }
  return `Live vision active on ${source} · backend loop · every 5s`;
});

function clearSnapshotObjectUrl() {
  if (snapshotObjectUrl) {
    URL.revokeObjectURL(snapshotObjectUrl);
    snapshotObjectUrl = null;
  }
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

async function refreshPcFrame() {
  try {
    const response = await fetch(`/api/vision/live-frame?t=${Date.now()}`);
    if (!response.ok) {
      pcCameraStatus.value = "Waiting for backend live vision frame...";
      return;
    }
    const blob = await response.blob();
    const nextUrl = URL.createObjectURL(blob);
    if (pcFrameSrc.value.startsWith("blob:")) {
      URL.revokeObjectURL(pcFrameSrc.value);
    }
    pcFrameSrc.value = nextUrl;
    pcCameraStatus.value = `Backend vision loop · ${String(props.visionStatus?.fps ?? 0)} fps`;
  } catch {
    pcCameraStatus.value = "Live vision frame unavailable.";
  }
}

function startPcFrameLoop() {
  stopPcFrameLoop();
  void refreshPcFrame();
  liveFrameTimer = window.setInterval(() => {
    void refreshPcFrame();
  }, LIVE_FRAME_MS);
}

function stopPcFrameLoop() {
  if (liveFrameTimer !== null) {
    window.clearInterval(liveFrameTimer);
    liveFrameTimer = null;
  }
  if (pcFrameSrc.value.startsWith("blob:")) {
    URL.revokeObjectURL(pcFrameSrc.value);
  }
  pcFrameSrc.value = "";
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

function applyCameraSource(cameraSource: CameraSource) {
  if (cameraSource === "pc") {
    startPcFrameLoop();
  } else {
    stopPcFrameLoop();
  }
}

watch(
  () => props.visionResult?.risk_map,
  (riskMap) => {
    if (riskMap) {
      emit("risk-map-update", riskMap);
    }
  },
);

onMounted(() => {
  applyCameraSource(props.cameraSource);
});

onUnmounted(() => {
  stopPcFrameLoop();
  clearSnapshotObjectUrl();
});

watch(
  () => props.cameraSource,
  (cameraSource, previous) => {
    if (cameraSource !== previous) {
      applyCameraSource(cameraSource);
    }
  },
);

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
      <small>{{ visionResult?.model_id ?? "gemini-robotics-er" }}</small>
    </div>

    <div class="recognition-toolbar">
      <div class="vlm-hud">
        <span class="hud-safe">SAFE {{ detectionCounts.SAFE }}</span>
        <span class="hud-danger">DANGER {{ detectionCounts.DANGER }}</span>
        <span class="hud-avoid">AVOID {{ detectionCounts.AVOID }}</span>
      </div>
      <span
        :class="[
          'vlm-status',
          {
            'vlm-status-loading': visionStatus?.vlm_state === 'analyzing',
            'vlm-status-error': Boolean(visionStatus?.last_error),
          },
        ]"
      >
        {{ vlmStatusText }}
      </span>
    </div>
    <p v-if="visionResult && !visionResult.valid && !visionStatus?.last_error" class="subtle">
      {{ visionResult.validation_errors?.join(" · ") || "VLM returned no valid detections." }}
    </p>

    <div v-if="cameraSource === 'pc'" class="live-feed-stage live-video-primary">
      <img
        v-if="pcFrameSrc"
        class="live-vision-frame"
        :src="pcFrameSrc"
        alt="Backend live vision frame"
      />
      <p v-else class="subtle live-vision-placeholder">Waiting for backend live vision loop...</p>
      <VideoFeedOverlay
        :detections="liveDetections"
        :risk-map="overlayRiskMap"
        observer-label="pc-camera"
      />
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
          <VideoFeedOverlay
            v-if="stream.robot_id === focusRobotId"
            :detections="liveDetections"
            :risk-map="overlayRiskMap"
            :observer-label="stream.robot_id"
          />
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

    <div
      v-if="visionResult?.classification"
      :class="[
        'classification',
        visionResult.classification.label === 'MINE'
          ? 'mine'
          : visionResult.classification.label === 'NOT_MINE'
            ? 'not_mine'
            : 'uncertain',
      ]"
    >
      Mission label: {{ visionResult.classification.label }}
      <small>{{ Math.round(visionResult.classification.confidence * 100) }}%</small>
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
