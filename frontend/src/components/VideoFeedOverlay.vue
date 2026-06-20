<script setup lang="ts">
import { computed } from "vue";
import type { RiskMapState } from "../types";

export interface FeedDetection {
  class?: string;
  risk?: string;
  confidence?: number;
  bbox?: number[];
}

const props = withDefaults(
  defineProps<{
    detections: FeedDetection[];
    riskMap?: RiskMapState | null;
    observerLabel?: string;
    showGrid?: boolean;
    showMinimap?: boolean;
  }>(),
  {
    riskMap: null,
    observerLabel: "observer",
    showGrid: true,
    showMinimap: true,
  },
);

const gridLines = Array.from({ length: 9 }, (_, index) => index + 1);

const minimapCols = computed(() => props.riskMap?.grid_cols ?? 9);
const minimapRows = computed(() => props.riskMap?.grid_rows ?? 6);

const minimapCells = computed(() => {
  const lookup = new Map<string, string>();
  for (const cell of props.riskMap?.cells ?? []) {
    lookup.set(`${cell.col}:${cell.row}`, cell.risk);
  }
  const cells: Array<{ col: number; row: number; risk: string | null }> = [];
  for (let row = 0; row < minimapRows.value; row += 1) {
    for (let col = 0; col < minimapCols.value; col += 1) {
      cells.push({
        col,
        row,
        risk: lookup.get(`${col}:${row}`) ?? null,
      });
    }
  }
  return cells;
});

function detectionOverlayStyle(bbox: number[] | undefined) {
  if (!bbox || bbox.length < 4 || Math.max(...bbox) > 1) {
    return null;
  }
  const [x, y, width, height] = bbox;
  return {
    left: `${(x * 100).toFixed(2)}%`,
    top: `${(y * 100).toFixed(2)}%`,
    width: `${(width * 100).toFixed(2)}%`,
    height: `${(height * 100).toFixed(2)}%`,
  };
}

function riskClassFromDetection(detection: FeedDetection) {
  if (detection.risk === "DANGER") return "mine";
  if (detection.risk === "SAFE") return "not_mine";
  return "uncertain";
}

function riskClassFromCell(risk: string | null) {
  if (risk === "DANGER") return "danger";
  if (risk === "SAFE") return "safe";
  if (risk === "AVOID") return "avoid";
  return "empty";
}

function detectionLabel(detection: FeedDetection) {
  const confidence = Math.round((detection.confidence ?? 0) * 100);
  const action =
    detection.risk === "SAFE"
      ? "LASCIA"
      : detection.risk === "DANGER"
        ? "RIMUOVI"
        : "EVITA+TRACCIA";
  return `${detection.risk ?? "?"} ${confidence}% → ${action}`;
}

function confidenceBarStyle(detection: FeedDetection) {
  const confidence = Math.max(0, Math.min(1, detection.confidence ?? 0));
  return { width: `${(confidence * 100).toFixed(0)}%` };
}
</script>

<template>
  <div class="video-feed-overlay" aria-hidden="true">
    <div v-if="showGrid" class="video-debug-grid">
      <div
        v-for="line in gridLines"
        :key="`v-${line}`"
        class="video-grid-line vertical"
        :style="{ left: `${(line * 10).toFixed(1)}%` }"
      />
      <div
        v-for="line in gridLines"
        :key="`h-${line}`"
        class="video-grid-line horizontal"
        :style="{ top: `${(line * 10).toFixed(1)}%` }"
      />
      <div class="video-center-crosshair" />
    </div>

    <div
      v-for="(detection, index) in detections"
      :key="`det-${index}`"
      :class="['live-detection-box', riskClassFromDetection(detection)]"
      :style="detectionOverlayStyle(detection.bbox) ?? undefined"
    >
      <span>{{ detectionLabel(detection) }}</span>
      <div class="live-detection-confidence">
        <div :class="['live-detection-confidence-fill', riskClassFromDetection(detection)]" :style="confidenceBarStyle(detection)" />
      </div>
    </div>

    <aside v-if="showMinimap" class="video-minimap">
      <header class="video-minimap-title">MAPPA · x=direzione · y=distanza</header>
      <div
        class="video-minimap-grid"
        :style="{
          gridTemplateColumns: `repeat(${minimapCols}, minmax(0, 1fr))`,
          gridTemplateRows: `repeat(${minimapRows}, minmax(0, 1fr))`,
        }"
      >
        <div
          v-for="cell in minimapCells"
          :key="`mini-${cell.col}-${cell.row}`"
          :class="['video-minimap-cell', riskClassFromCell(cell.risk)]"
        />
      </div>
      <div class="video-minimap-axis">
        <span>lontano</span>
        <span>vicino</span>
      </div>
      <div class="video-minimap-observer">
        <span class="observer-marker">▲</span>
        <small>{{ riskMap?.observer_robot_id ?? observerLabel }}</small>
      </div>
    </aside>
  </div>
</template>
