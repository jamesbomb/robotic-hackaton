<script setup lang="ts">
import { ref } from "vue";

const emit = defineEmits<{
  command: [text: string, scenario: string];
}>();

const text = ref("ispeziona settore B2 con scenario dubbio");
const scenario = ref("MINE");

function submit() {
  emit("command", text.value, scenario.value);
}
</script>

<template>
  <section class="panel command-palette">
    <div class="panel-title">
      <span>Command Palette</span>
      <small>allow-listed intent</small>
    </div>
    <textarea v-model="text" rows="3" />
    <select v-model="scenario">
      <option>MINE</option>
      <option>NOT_MINE</option>
      <option>UNCERTAIN</option>
    </select>
    <button @click="submit">Send Command</button>
  </section>
</template>
