<script setup lang="ts">
import { computed, ref } from "vue";
import CollapsiblePanel from "./CollapsiblePanel.vue";
import type { ObjectPickupSession } from "../types";

const props = defineProps<{
  activeSession: ObjectPickupSession | null;
  sessions: ObjectPickupSession[];
  busy: boolean;
}>();
const emit = defineEmits<{
  start: [operatorId: string, objectLabel: string];
  finish: [sessionId: string | null];
  replay: [sessionId: string, operatorId: string];
}>();

const operatorId = ref("operator");
const objectLabel = ref("safe_object");

const savedSessions = computed(() =>
  props.sessions.filter((session) => session.status !== "recording"),
);

function startRecording() {
  emit("start", operatorId.value || "operator", objectLabel.value || "safe_object");
}
</script>

<template>
  <CollapsiblePanel
    title="Object Pickup Workflow"
    :meta="activeSession?.status ?? `${savedSessions.length} templates`"
    panel-class="object-pickup-panel"
    default-open
  >
    <p>
      Composite flow: Go2 low posture, SO-101 human takeover with video context, then save
      the manual arm sequence as a reusable template.
    </p>

    <label>
      Operator
      <input v-model="operatorId" :disabled="busy" />
    </label>

    <label>
      Object label
      <input v-model="objectLabel" :disabled="busy || Boolean(activeSession)" />
    </label>

    <div class="pickup-actions">
      <button :disabled="busy || Boolean(activeSession)" @click="startRecording">
        Start Recording
      </button>
      <button
        :disabled="busy || !activeSession"
        @click="emit('finish', activeSession?.session_id ?? null)"
      >
        Finish / Save
      </button>
    </div>

    <article v-if="activeSession" class="pickup-session-card recording">
      <strong>{{ activeSession.object_label }}</strong>
      <small>{{ activeSession.session_id }}</small>
      <span>Steps: {{ activeSession.steps.length }}</span>
      <span>Go2 posture: {{ activeSession.go2_posture_action }}</span>
      <span>Video refs: {{ activeSession.camera_streams.length }}</span>
    </article>

    <div v-if="activeSession?.camera_streams.length" class="pickup-video-list">
      <span v-for="stream in activeSession.camera_streams" :key="stream.twin_id">
        {{ stream.robot_id }} · {{ stream.browser_url }}
      </span>
    </div>

    <div v-if="savedSessions.length" class="pickup-template-list">
      <article
        v-for="session in savedSessions"
        :key="session.session_id"
        class="pickup-session-card"
      >
        <strong>{{ session.object_label }}</strong>
        <small>{{ session.session_id }}</small>
        <span>Steps: {{ session.steps.length }}</span>
        <span>Replays: {{ session.replay_count }}</span>
        <button
          :disabled="busy"
          @click="emit('replay', session.session_id, operatorId || 'operator')"
        >
          Reuse Template
        </button>
      </article>
    </div>

    <p v-else class="subtle">No saved pickup template yet.</p>
  </CollapsiblePanel>
</template>
