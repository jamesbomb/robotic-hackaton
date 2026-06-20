<script setup lang="ts">
import CollapsiblePanel from "./CollapsiblePanel.vue";
import type { EventRecord } from "../types";

defineProps<{ events: EventRecord[] }>();
</script>

<template>
  <CollapsiblePanel title="Audit Timeline" :meta="`${events.length} events`" panel-class="timeline">
    <ol>
      <li v-for="event in events.slice().reverse()" :key="`${event.timestamp}-${event.event_type}`">
        <time>{{ new Date(event.timestamp).toLocaleTimeString() }}</time>
        <strong>{{ event.event_type }}</strong>
        <span>{{ event.robot_id ?? "system" }}</span>
      </li>
    </ol>
  </CollapsiblePanel>
</template>
