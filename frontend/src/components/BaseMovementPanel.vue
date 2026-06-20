<script setup lang="ts">
import { computed, ref } from "vue";
import CollapsiblePanel from "./CollapsiblePanel.vue";
import type { BaseMovementAction, BaseMovementCommandRequest, RobotStatus } from "../types";

const props = defineProps<{ robots: RobotStatus[]; busy: boolean }>();
const emit = defineEmits<{
  move: [robotId: string, command: BaseMovementCommandRequest];
}>();

const operatorId = ref("operator");
const selectedRobotId = ref("go2");
const distanceM = ref(0.25);
const angleDegrees = ref(10);

const mobileRobots = computed(() =>
  props.robots.filter((robot) => robot.actions.includes("move_forward")),
);

const selectedRobot = computed(
  () => mobileRobots.value.find((robot) => robot.robot_id === selectedRobotId.value) ?? null,
);

function send(action: BaseMovementAction) {
  const robot = selectedRobot.value;
  if (!robot) {
    return;
  }

  emit("move", robot.robot_id, {
    action,
    operator_id: operatorId.value || "operator",
    operator_confirmed: true,
    distance_m: distanceM.value,
    angle_degrees: angleDegrees.value,
    reason: "Operator requested bounded P0 base movement from the dashboard.",
  });
}
</script>

<template>
  <CollapsiblePanel
    title="Base Movement P0"
    :meta="selectedRobot?.robot_id ?? 'no mobile robot'"
    panel-class="base-movement-panel"
  >
    <p>
      Micro-movements are operator-confirmed, stop-wrapped, and limited to 0.5 m or 15
      degrees.
    </p>

    <label>
      Robot
      <select v-model="selectedRobotId" :disabled="busy || mobileRobots.length === 0">
        <option v-for="robot in mobileRobots" :key="robot.robot_id" :value="robot.robot_id">
          {{ robot.robot_id }}
        </option>
      </select>
    </label>

    <label>
      Operator
      <input v-model="operatorId" :disabled="busy || !selectedRobot" />
    </label>

    <div class="movement-values">
      <label>
        Distance m
        <input v-model.number="distanceM" type="number" min="0.05" max="0.5" step="0.05" />
      </label>
      <label>
        Angle deg
        <input v-model.number="angleDegrees" type="number" min="1" max="15" step="1" />
      </label>
    </div>

    <div class="movement-grid">
      <button :disabled="busy || !selectedRobot" @click="send('move_forward')">Forward</button>
      <button :disabled="busy || !selectedRobot" @click="send('move_backward')">Backward</button>
      <button :disabled="busy || !selectedRobot" @click="send('rotate_left')">Rotate L</button>
      <button :disabled="busy || !selectedRobot" @click="send('rotate_right')">Rotate R</button>
    </div>
  </CollapsiblePanel>
</template>
