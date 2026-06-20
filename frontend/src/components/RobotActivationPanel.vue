<script setup lang="ts">
import { computed, ref } from "vue";
import CollapsiblePanel from "./CollapsiblePanel.vue";
import type {
  CyberwaveRobot,
  RobotActivationMode,
  RobotActivationRequest,
  RobotActivationState,
  RuntimeMode,
} from "../types";

const props = defineProps<{
  cyberwaveRobots: CyberwaveRobot[];
  activations: RobotActivationState[];
  runtimeMode: RuntimeMode;
  dryRun: boolean;
  busy: boolean;
}>();
const emit = defineEmits<{
  activate: [robotId: string, command: RobotActivationRequest];
}>();

const operatorId = ref("operator");

const activationByRobot = computed(() =>
  Object.fromEntries(props.activations.map((activation) => [activation.robot_id, activation])),
);

function canArmPhysical() {
  return props.runtimeMode === "live" && !props.dryRun;
}

function activate(robotId: string, mode: RobotActivationMode) {
  const allowPhysical = mode === "armed";
  emit("activate", robotId, {
    operator_id: operatorId.value || "operator",
    operator_confirmed: true,
    activation_mode: mode,
    allow_physical: allowPhysical,
    reason:
      mode === "armed"
        ? "Operator armed robot for supervised physical movement."
        : "Operator marked robot ready for virtual/simulation movement.",
  });
}
</script>

<template>
  <CollapsiblePanel
    title="Robot Activation"
    :meta="`${cyberwaveRobots.length} Cyberwave twins`"
    panel-class="robot-activation-panel"
    default-open
  >
    <p>
      Activate robots before movement. Virtual movement updates the dashboard twin;
      physical movement requires <code>live</code>, dry-run disabled, and an armed robot.
    </p>

    <label>
      Operator
      <input v-model="operatorId" :disabled="busy" />
    </label>

    <article
      v-for="robot in cyberwaveRobots"
      :key="robot.twin_uuid"
      class="activation-card"
    >
      <div class="activation-card__top">
        <strong>{{ robot.name }}</strong>
        <span>{{ robot.robot_id }}</span>
      </div>
      <small>{{ robot.twin_uuid }}</small>
      <div class="robot-meta">
        <span>{{ robot.registry_id ?? "unknown asset" }}</span>
        <span>{{ robot.has_stream ? "stream ready" : "no stream" }}</span>
        <span>{{ activationByRobot[robot.robot_id]?.armed ? "armed" : activationByRobot[robot.robot_id]?.ready ? "ready" : "available" }}</span>
      </div>
      <div class="activation-actions">
        <button :disabled="busy" @click="activate(robot.robot_id, 'ready')">
          Ready Virtual
        </button>
        <button
          :disabled="busy || !canArmPhysical()"
          class="danger"
          @click="activate(robot.robot_id, 'armed')"
        >
          Arm Physical
        </button>
      </div>
    </article>

    <p v-if="!canArmPhysical()" class="subtle">
      Physical arming is disabled until Safety is set to live and dry-run is off.
    </p>
  </CollapsiblePanel>
</template>
