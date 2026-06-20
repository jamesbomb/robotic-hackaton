<script setup lang="ts">
import { computed, ref } from "vue";
import type { MapPoint, ScoutRouteResult } from "../types";

const props = defineProps<{
  busy: boolean;
  route: ScoutRouteResult | null;
}>();

const emit = defineEmits<{
  plan: [waypoints: MapPoint[]];
}>();

const draft = ref<MapPoint[]>([
  { x: 0.12, y: 0.78 },
  { x: 0.38, y: 0.56 },
  { x: 0.74, y: 0.34 },
]);

const pathPoints = computed(() =>
  draft.value.map((point) => `${point.x * 100},${point.y * 100}`).join(" "),
);

const routePathPoints = computed(() =>
  (props.route?.waypoints ?? []).map((point) => `${point.x * 100},${point.y * 100}`).join(" "),
);

function addWaypoint(event: MouseEvent) {
  const svg = event.currentTarget as SVGSVGElement;
  const rect = svg.getBoundingClientRect();
  const x = (event.clientX - rect.left) / rect.width;
  const y = (event.clientY - rect.top) / rect.height;
  draft.value = [...draft.value, { x: clamp(x), y: clamp(y) }].slice(0, 12);
}

function clamp(value: number) {
  return Math.min(1, Math.max(0, Number(value.toFixed(3))));
}

function clear() {
  draft.value = [];
}

function submit() {
  if (draft.value.length >= 2) {
    emit("plan", draft.value);
  }
}
</script>

<template>
  <section class="panel scout-route-panel">
    <div class="panel-title">
      <span>Scout Route Planner</span>
      <small>Unitree Go2 / dry-run</small>
    </div>

    <svg class="route-canvas" viewBox="0 0 100 100" role="img" @click="addWaypoint">
      <defs>
        <pattern id="route-grid" width="10" height="10" patternUnits="userSpaceOnUse">
          <path d="M 10 0 L 0 0 0 10" fill="none" stroke="rgba(122,255,190,0.14)" stroke-width="0.4" />
        </pattern>
      </defs>
      <rect width="100" height="100" fill="url(#route-grid)" />
      <polyline v-if="routePathPoints" :points="routePathPoints" class="accepted-route" />
      <polyline v-if="pathPoints" :points="pathPoints" class="draft-route" />

      <circle
        v-for="obstacle in route?.obstacles ?? []"
        :key="obstacle.obstacle_id"
        :cx="obstacle.position.x * 100"
        :cy="obstacle.position.y * 100"
        :r="obstacle.radius * 100"
        class="route-obstacle"
      />
      <circle
        v-for="(point, index) in draft"
        :key="`${point.x}-${point.y}-${index}`"
        :cx="point.x * 100"
        :cy="point.y * 100"
        r="2.2"
        class="route-waypoint"
      />
    </svg>

    <div class="route-actions">
      <button type="button" :disabled="busy || draft.length < 2" @click="submit">
        Plan Go2 Route
      </button>
      <button type="button" :disabled="busy" @click="clear">Clear</button>
    </div>

    <p class="subtle">
      Click on the map to add waypoints. Planning is audited and stays dry-run until a real Cyberwave
      navigation adapter is added.
    </p>

    <dl v-if="route" class="data-list">
      <div>
        <dt>Route</dt>
        <dd>{{ route.route_id }}</dd>
      </div>
      <div>
        <dt>Waypoints</dt>
        <dd>{{ route.waypoints.length }}</dd>
      </div>
      <div>
        <dt>Obstacles</dt>
        <dd>{{ route.obstacles.length }}</dd>
      </div>
    </dl>
  </section>
</template>
