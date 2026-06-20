<script setup lang="ts">
import type { EventRecord } from "../types";

defineProps<{ events: EventRecord[] }>();
</script>

<template>
  <section class="panel timeline">
    <div class="panel-title">
      <span>Audit Timeline</span>
      <small>{{ events.length }} events</small>
    </div>
    <ol>
      <li v-for="event in events.slice().reverse()" :key="`${event.timestamp}-${event.event_type}`">
        <time>{{ new Date(event.timestamp).toLocaleTimeString() }}</time>
        <strong>{{ event.event_type }}</strong>
        <span>{{ event.robot_id ?? "system" }}</span>
      </li>
    </ol>
  </section>
</template>
