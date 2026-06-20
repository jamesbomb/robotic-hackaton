<script setup lang="ts">
import { ref } from "vue";

const emit = defineEmits<{
  command: [text: string, scenario: string];
}>();

const commandInput = ref<HTMLTextAreaElement | null>(null);
const text = ref("ispeziona il campo in cerca di mine");
const scenario = ref("FIELD");

function submit() {
  emit("command", text.value, scenario.value);
}

function focus() {
  commandInput.value?.focus();
}

function hasFocus() {
  return commandInput.value === document.activeElement;
}

defineExpose({ focus, hasFocus, submit });
</script>

<template>
  <section class="panel command-palette">
    <div class="panel-title">
      <span>Command Palette</span>
      <small>allow-listed intent</small>
    </div>
    <textarea ref="commandInput" v-model="text" rows="3" />
    <select v-model="scenario">
      <option>FIELD</option>
      <option>MINE</option>
      <option>NOT_MINE</option>
      <option>UNCERTAIN</option>
    </select>
    <button @click="submit">Send Command <kbd>Ctrl</kbd>+<kbd>Enter</kbd></button>
  </section>
</template>
