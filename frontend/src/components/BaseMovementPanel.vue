<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import CollapsiblePanel from "./CollapsiblePanel.vue";
import type {
  BaseMovementAction,
  BaseMovementCommandRequest,
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
  busy: boolean;
}>();
const emit = defineEmits<{
  move: [robotId: string, command: BaseMovementCommandRequest];
  stop: [];
}>();

const operatorId = ref("operator");
const selectedRobotId = ref("go2");
const distanceM = ref(0.25);
const angleDegrees = ref(10);
const movementTarget = ref<MovementTarget>("virtual");
const keyboardEnabled = ref(false);

const keyBindings: { key: string; label: string; action: BaseMovementAction }[] = [
  { key: "W / ↑", label: "Forward", action: "move_forward" },
  { key: "S / ↓", label: "Backward", action: "move_backward" },
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

function isEditableTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  return Boolean(
    target.closest("input, select, textarea, button") || target.isContentEditable,
  );
}

function actionFromKey(key: string): BaseMovementAction | null {
  const normalized = key.toLowerCase();
  if (normalized === "w" || key === "ArrowUp") {
    return "move_forward";
  }
  if (normalized === "s" || key === "ArrowDown") {
    return "move_backward";
  }
  if (normalized === "a" || normalized === "q" || key === "ArrowLeft") {
    return "rotate_left";
  }
  if (normalized === "d" || normalized === "e" || key === "ArrowRight") {
    return "rotate_right";
  }
  return null;
}

function handleKeydown(event: KeyboardEvent) {
  if (!keyboardEnabled.value || props.busy || event.repeat || isEditableTarget(event.target)) {
    return;
  }
  if (event.key === "Escape") {
    keyboardEnabled.value = false;
    return;
  }
  if (event.key === " ") {
    event.preventDefault();
    emit("stop");
    return;
  }

  const action = actionFromKey(event.key);
  if (action === null) {
    return;
  }
  event.preventDefault();
  send(action);
}

onMounted(() => {
  window.addEventListener("keydown", handleKeydown);
});

onUnmounted(() => {
  window.removeEventListener("keydown", handleKeydown);
});
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
