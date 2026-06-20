<script setup lang="ts">
import type { Finding, Observation, RobotStatus } from "../types";

defineProps<{
  robots: RobotStatus[];
  observations: Observation[];
  finding: Finding | null;
}>();
</script>

<template>
  <section class="panel map-panel">
    <div class="panel-title">
      <span>Risk Map</span>
      <small>demo grid</small>
    </div>
    <div class="grid-map">
      <div v-for="robot in robots" :key="robot.robot_id" class="map-entity robot-entity">
        <span>{{ robot.robot_id }}</span>
        <small>x{{ robot.pose.x.toFixed(1) }} y{{ robot.pose.y.toFixed(1) }}</small>
      </div>
      <div
        v-if="finding"
        :class="['map-entity', 'finding-entity', finding.label.toLowerCase()]"
      >
        <span>{{ finding.label }}</span>
        <small>{{ Math.round(finding.confidence * 100) }}% confidence</small>
      </div>
    </div>
    <div class="observation-strip">
      <div v-for="observation in observations" :key="observation.observation_id">
        <strong>{{ observation.robot_id }}</strong>
        <span>{{ observation.classification.label }}</span>
        <small>{{ observation.sensor_id }}</small>
      </div>
    </div>
  </section>
</template>
