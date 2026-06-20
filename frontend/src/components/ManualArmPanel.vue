<script setup lang="ts">
import { computed, ref } from "vue";
import type { ManualArmAction, ManualArmCommandRequest, RobotStatus } from "../types";

const props = defineProps<{ robot: RobotStatus | null; busy: boolean }>();
const emit = defineEmits<{
  manualCommand: [robotId: string, command: ManualArmCommandRequest];
}>();

const jointName = ref("shoulder");
const stepDegrees = ref(2);
const operatorId = ref("operator");

const isAvailable = computed(() => Boolean(props.robot?.actions.includes("manual_arm_nudge_joint")));

function send(action: ManualArmAction) {
  if (!props.robot) {
    return;
  }

  const command: ManualArmCommandRequest = {
    action,
    operator_id: operatorId.value || "operator",
    operator_confirmed: true,
    reason: "Operator requested SO-101 manual takeover from the dashboard.",
  };

  if (action === "nudge_joint") {
    command.joint_name = jointName.value;
    command.delta_degrees = stepDegrees.value;
  }

  if (action === "place_safe_marker") {
    command.target_label = "NOT_MINE";
  }

  emit("manualCommand", props.robot.robot_id, command);
}
</script>

<template>
  <section class="panel manual-arm-panel">
    <div class="panel-title">
      <span>SO-101 Takeover</span>
      <small>{{ robot?.task ?? "offline" }}</small>
    </div>

    <p>
      Human operator controls are bounded and audited. Marker placement is only sent as a
      prevalidated safe preset for <code>NOT_MINE</code> targets.
    </p>

    <label>
      Operator
      <input v-model="operatorId" :disabled="busy || !robot" />
    </label>

    <div class="manual-arm-grid">
      <button :disabled="busy || !robot" @click="send('home')">Home</button>
      <button :disabled="busy || !robot" @click="send('hold_position')">Hold</button>
      <button :disabled="busy || !robot || !isAvailable" @click="send('place_safe_marker')">
        Safe Marker
      </button>
    </div>

    <div class="manual-arm-nudge">
      <label>
        Joint
        <select v-model="jointName" :disabled="busy || !robot">
          <option value="base">base</option>
          <option value="shoulder">shoulder</option>
          <option value="elbow">elbow</option>
          <option value="wrist_pitch">wrist_pitch</option>
          <option value="wrist_roll">wrist_roll</option>
          <option value="gripper">gripper</option>
        </select>
      </label>
      <label>
        Step degrees
        <input v-model.number="stepDegrees" type="number" min="-5" max="5" step="0.5" />
      </label>
      <button :disabled="busy || !robot || !isAvailable" class="full" @click="send('nudge_joint')">
        Nudge Joint
      </button>
    </div>
  </section>
</template>
