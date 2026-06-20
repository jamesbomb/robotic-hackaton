<script setup lang="ts">
import CollapsiblePanel from "./CollapsiblePanel.vue";
import type { EventRecord } from "../types";

defineProps<{ events: EventRecord[] }>();

function eventDetail(event: EventRecord): string {
  if (event.event_type === "CYBERWAVE_MOVEMENT_FEED") {
    const position = event.data?.position as Record<string, number> | undefined;
    const rotation = event.data?.rotation as Record<string, number> | undefined;
    const feed = String(event.data?.feed ?? "movement");
    if (position) {
      const x = typeof position.x === "number" ? position.x.toFixed(2) : "?";
      const y = typeof position.y === "number" ? position.y.toFixed(2) : "?";
      const z = typeof position.z === "number" ? position.z.toFixed(2) : "?";
      return `${feed} x=${x} y=${y} z=${z}`;
    }
    if (rotation && typeof rotation.yaw === "number") {
      return `${feed} yaw=${rotation.yaw.toFixed(1)}°`;
    }
    return feed;
  }
  if (event.event_type === "CYBERWAVE_MOVEMENT_FEED_STARTED") {
    const robots = event.data?.robots;
    const affect = event.data?.affect_mode;
    const robotList = Array.isArray(robots) ? robots.join(", ") : "robots";
    return `subscribed ${robotList}${affect ? ` · ${affect}` : ""}`;
  }
  if (event.event_type === "CYBERWAVE_MOVEMENT_FEED_STOPPED") {
    return "movement feed disconnected";
  }
  if (event.event_type === "RISK_MAP_UPDATED") {
    const riskMap = event.data?.risk_map as { counts?: Record<string, number> } | undefined;
    const counts = riskMap?.counts;
    if (counts) {
      return `SAFE ${counts.SAFE ?? 0} · DANGER ${counts.DANGER ?? 0} · AVOID ${counts.AVOID ?? 0}`;
    }
  }
  if (event.event_type === "VISION_CLASSIFIED") {
    const count = event.data?.detection_count;
    return typeof count === "number" ? `${count} detections` : "vision classified";
  }
  if (event.event_type === "VISION_LOOP_STARTED") {
    return "live vision worker started";
  }
  if (event.event_type === "VISION_LOOP_STOPPED") {
    return "live vision worker stopped";
  }
  return "";
}
</script>

<template>
  <CollapsiblePanel title="Audit Timeline" :meta="`${events.length} events`" panel-class="timeline">
    <ol>
      <li
        v-for="(event, index) in events.slice().reverse()"
        :key="`${event.timestamp}-${event.event_type}-${index}`"
      >
        <time>{{ new Date(event.timestamp).toLocaleTimeString() }}</time>
        <strong>{{ event.event_type }}</strong>
        <span>{{ event.robot_id ?? "system" }}</span>
        <small v-if="eventDetail(event)">{{ eventDetail(event) }}</small>
      </li>
    </ol>
  </CollapsiblePanel>
</template>
