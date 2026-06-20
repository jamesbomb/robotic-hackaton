<script setup lang="ts">
import { computed, ref, watch } from "vue";
import CollapsiblePanel from "./CollapsiblePanel.vue";
import type {
  BaseMovementAction,
  BaseMovementCommandRequest,
  MovementCommandRequest,
  MovementControllerState,
  MovementTarget,
  RobotActivationState,
  RobotStatus,
  RuntimeMode,
} from "../types";

const props = defineProps<{
  robots: RobotStatus[];
  activations: RobotActivationState[];
  runtimeMode: RuntimeMode;
  dryRun: boolean;
  movementController: MovementControllerState;
  busy: boolean;
  keyboardDriveEnabled: boolean;
}>();
const emit = defineEmits<{
  move: [robotId: string, command: BaseMovementCommandRequest];
  movementCommand: [command: MovementCommandRequest];
  stopRobot: [robotId: string];
  stop: [];
  "update:keyboardDriveEnabled": [enabled: boolean];
  keyboardConfigChange: [
    config: {
      enabled: boolean;
      robotId: string;
      movementTarget: MovementTarget;
      distanceM: number;
      angleDegrees: number;
    },
  ];
}>();

const operatorId = ref("operator");
const selectedRobotId = ref("go2");
const distanceM = ref(0.25);
const angleDegrees = ref(10);
const movementTarget = ref<MovementTarget>("virtual");
const keyboardEnabled = ref(props.keyboardDriveEnabled);
const movementText = ref("avanti");

const keyBindings: { key: string; label: string; action: BaseMovementAction }[] = [
  { key: "W / ↑", label: "Forward", action: "move_forward" },
  { key: "S / ↓", label: "Backward", action: "move_backward" },
  { key: "Shift+A", label: "Strafe left", action: "strafe_left" },
  { key: "Shift+D", label: "Strafe right", action: "strafe_right" },
  { key: "A / ←", label: "Rotate left", action: "rotate_left" },
  { key: "D / →", label: "Rotate right", action: "rotate_right" },
  { key: "Q", label: "Rotate left", action: "rotate_left" },
  { key: "E", label: "Rotate right", action: "rotate_right" },
];

const mobileRobots = computed(() =>
  props.robots.filter((robot) => robot.actions.includes("move_forward")),
);

const selectedRobot = computed(
  () => mobileRobots.value.find((robot) => robot.robot_id === selectedRobotId.value) ?? null,
);
const selectedActivation = computed(
  () => props.activations.find((activation) => activation.robot_id === selectedRobotId.value) ?? null,
);
const canUsePhysical = computed(
  () =>
    props.runtimeMode === "live" &&
    !props.dryRun &&
    Boolean(selectedActivation.value?.armed && selectedActivation.value.physical_enabled),
);

function send(action: BaseMovementAction) {
  const robot = selectedRobot.value;
  if (!robot) {
    return;
  }

  emit("move", robot.robot_id, {
    action,
    movement_target: movementTarget.value,
    operator_id: operatorId.value || "operator",
    operator_confirmed: true,
    distance_m: distanceM.value,
    angle_degrees: angleDegrees.value,
    reason: "Operator requested bounded P0 base movement from the dashboard.",
  });
}

function sendMovementText() {
  emit("movementCommand", {
    text: movementText.value,
    robot_id: "go2",
    movement_target: movementTarget.value,
    operator_id: operatorId.value || "operator",
    operator_confirmed: true,
    distance_m: distanceM.value,
    angle_degrees: angleDegrees.value,
    reason: "Operator requested LLM-assisted Go2 movement from dashboard.",
  });
}

watch(
  [keyboardEnabled, selectedRobotId, movementTarget, distanceM, angleDegrees],
  () => {
    emit("update:keyboardDriveEnabled", keyboardEnabled.value);
    emit("keyboardConfigChange", {
      enabled: keyboardEnabled.value,
      robotId: selectedRobotId.value,
      movementTarget: movementTarget.value,
      distanceM: distanceM.value,
      angleDegrees: angleDegrees.value,
    });
  },
  { immediate: true },
);

watch(
  () => props.keyboardDriveEnabled,
  (enabled) => {
    keyboardEnabled.value = enabled;
  },
);
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

    <label>
      Movement target
      <select v-model="movementTarget" :disabled="busy || !selectedRobot">
        <option value="virtual">Virtual dashboard twin</option>
        <option value="auto">Auto safe default</option>
        <option :disabled="!canUsePhysical" value="physical">Physical robot</option>
        <option :disabled="!canUsePhysical" value="both">Both virtual + physical</option>
      </select>
    </label>
    <p class="subtle">
      Physical targets require live mode, dry-run off, and an armed robot.
    </p>

    <div class="keyboard-control">
      <label class="inline-check">
        <input v-model="keyboardEnabled" type="checkbox" :disabled="busy || !selectedRobot" />
        Enable keyboard driving
      </label>
      <p class="subtle">
        Single key press sends one bounded command. Holding a key does not stream velocity.
        <code>Space</code> stops all, <code>Esc</code> disables keyboard driving.
      </p>
      <div class="keymap-grid">
        <span v-for="binding in keyBindings" :key="binding.key">
          <kbd>{{ binding.key }}</kbd>
          {{ binding.label }}
        </span>
      </div>
    </div>

    <div class="movement-agent-control">
      <div class="panel-title compact">
        <span>Go2 LLM Movement FSM</span>
        <small>{{ movementController.state }}</small>
      </div>
      <p class="subtle">{{ movementController.reason }}</p>
      <label>
        Movement command
        <input
          v-model="movementText"
          :disabled="busy"
          placeholder="avanti, indietro, ruota a sinistra..."
        />
      </label>
      <div class="movement-agent-actions">
        <button :disabled="busy || !movementText.trim()" @click="sendMovementText">
          Run Go2 Command
        </button>
        <button class="danger-button" @click="emit('stopRobot', 'go2')">
          Stop Go2
        </button>
      </div>
      <small v-if="movementController.last_plan">
        Last plan: {{ movementController.last_plan.action ?? "rejected" }}
      </small>
    </div>

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
      <button :disabled="busy || !selectedRobot" @click="send('strafe_left')">Strafe L</button>
      <button :disabled="busy || !selectedRobot" @click="send('strafe_right')">Strafe R</button>
      <button :disabled="busy || !selectedRobot" @click="send('rotate_left')">Rotate L</button>
      <button :disabled="busy || !selectedRobot" @click="send('rotate_right')">Rotate R</button>
    </div>
  </CollapsiblePanel>
</template>
