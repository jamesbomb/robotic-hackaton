<script setup lang="ts">
defineProps<{ open: boolean }>();

defineEmits<{
  close: [];
}>();

const groups = [
  {
    title: "Safety",
    shortcuts: [
      ["Space", "Emergency Stop All"],
      ["Esc", "Emergency Stop All / close overlays"],
    ],
  },
  {
    title: "Movement",
    shortcuts: [
      ["W / Up", "Go2 forward"],
      ["S / Down", "Go2 backward"],
      ["Shift + A", "Go2 strafe left"],
      ["Shift + D", "Go2 strafe right"],
      ["A / Left", "Go2 rotate left"],
      ["D / Right", "Go2 rotate right"],
    ],
  },
  {
    title: "Mission",
    shortcuts: [
      ["F", "Start Field Scan"],
      ["Ctrl/Cmd + K", "Focus Command Palette"],
      ["Ctrl/Cmd + Enter", "Send command from palette"],
    ],
  },
  {
    title: "Perception",
    shortcuts: [
      ["M", "Mark latest object as MINE"],
      ["N", "Mark latest object as NOT_MINE"],
      ["U", "Mark latest object as UNCERTAIN"],
    ],
  },
  {
    title: "Route / Arm",
    shortcuts: [
      ["R", "Plan current Go2 route"],
      ["C", "Clear draft route"],
      ["H", "SO-101 hold position"],
      ["?", "Toggle this help"],
    ],
  },
];
</script>

<template>
  <div v-if="open" class="shortcut-overlay" role="dialog" aria-modal="true">
    <section class="shortcut-card">
      <div class="panel-title">
        <span>Keyboard Shortcuts</span>
        <button type="button" @click="$emit('close')">Close</button>
      </div>
      <p class="subtle">
        Shortcuts are ignored while typing in form fields. Movement keys require Keyboard Drive
        enabled and send one bounded command per key press, never continuous velocity.
      </p>
      <div class="shortcut-grid">
        <article v-for="group in groups" :key="group.title">
          <h3>{{ group.title }}</h3>
          <dl>
            <div v-for="[key, label] in group.shortcuts" :key="key">
              <dt><kbd>{{ key }}</kbd></dt>
              <dd>{{ label }}</dd>
            </div>
          </dl>
        </article>
      </div>
    </section>
  </div>
</template>
