<script setup lang="ts">
import { computed } from "vue";
import type { Finding, RiskMapState } from "../types";

const props = defineProps<{
  riskMap: RiskMapState | null;
  finding: Finding | null;
}>();

const emit = defineEmits<{
  clear: [];
}>();

const cols = computed(() => props.riskMap?.grid_cols ?? 9);
const rows = computed(() => props.riskMap?.grid_rows ?? 6);
const counts = computed(
  () => props.riskMap?.counts ?? { SAFE: 0, DANGER: 0, AVOID: 0 },
);

const cellLookup = computed(() => {
  const lookup = new Map<string, string>();
  for (const cell of props.riskMap?.cells ?? []) {
    lookup.set(`${cell.col}:${cell.row}`, cell.risk);
  }
  return lookup;
});

const gridCells = computed(() => {
  const cells: Array<{ col: number; row: number; risk: string | null }> = [];
  for (let row = 0; row < rows.value; row += 1) {
    for (let col = 0; col < cols.value; col += 1) {
      cells.push({
        col,
        row,
        risk: cellLookup.value.get(`${col}:${row}`) ?? null,
      });
    }
  }
  return cells;
});

const updatedLabel = computed(() => {
  const updatedAt = props.riskMap?.updated_at;
  if (!updatedAt) {
    return "waiting for VLM";
  }
  return new Date(updatedAt).toLocaleTimeString();
});

function riskClass(risk: string | null) {
  if (risk === "DANGER") return "danger";
  if (risk === "SAFE") return "safe";
  if (risk === "AVOID") return "avoid";
  return "empty";
}
</script>

<template>
  <section class="panel map-panel">
    <div class="panel-title">
      <span>Risk Map</span>
      <small>x=direzione · y=distanza</small>
    </div>

    <div class="risk-map-hud">
      <span class="hud-safe">SAFE {{ counts.SAFE ?? 0 }}</span>
      <span class="hud-danger">DANGER {{ counts.DANGER ?? 0 }}</span>
      <span class="hud-avoid">AVOID {{ counts.AVOID ?? 0 }}</span>
      <span class="subtle">{{ riskMap?.observer_robot_id ?? "observer" }} · {{ updatedLabel }}</span>
      <button type="button" class="risk-map-clear" @click="emit('clear')">Clear</button>
    </div>

    <div class="risk-map-stage">
      <div
        class="risk-grid"
        :style="{
          gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
          gridTemplateRows: `repeat(${rows}, minmax(0, 1fr))`,
        }"
      >
        <div
          v-for="cell in gridCells"
          :key="`${cell.col}-${cell.row}`"
          :class="['risk-cell', riskClass(cell.risk)]"
          :title="cell.risk ? `${cell.risk} @ ${cell.col},${cell.row}` : `empty @ ${cell.col},${cell.row}`"
        />
      </div>
      <div class="risk-map-labels">
        <span>lontano</span>
        <span>vicino</span>
      </div>
      <div class="risk-map-observer">
        <span class="observer-marker">▲</span>
        <small>{{ riskMap?.observer_robot_id ?? "go2" }}</small>
      </div>
    </div>

    <div v-if="finding" :class="['risk-finding', finding.label.toLowerCase()]">
      Mission finding: {{ finding.label }}
      <small>{{ Math.round(finding.confidence * 100) }}%</small>
    </div>
  </section>
</template>
