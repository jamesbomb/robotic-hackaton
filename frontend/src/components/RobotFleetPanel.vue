<script setup lang="ts">
import CollapsiblePanel from "./CollapsiblePanel.vue";
import type { RobotStatus } from "../types";

defineProps<{ robots: RobotStatus[] }>();
</script>

<template>
  <CollapsiblePanel title="Fleet" :meta="`${robots.length} entities`">
    <article v-for="robot in robots" :key="robot.robot_id" class="robot-card">
      <div class="robot-card__top">
        <strong>{{ robot.robot_id }}</strong>
        <span :class="['dot', robot.online ? 'online' : 'offline']"></span>
      </div>
      <p>{{ robot.role }}</p>
      <div class="robot-meta">
        <span>{{ robot.task }}</span>
        <span>{{ robot.battery_percent ?? "n/a" }}%</span>
        <span>{{ robot.mode }}</span>
      </div>
      <div class="chips">
        <span v-for="sensor in robot.sensors" :key="sensor">{{ sensor }}</span>
      </div>
    </article>
  </CollapsiblePanel>
</template>
