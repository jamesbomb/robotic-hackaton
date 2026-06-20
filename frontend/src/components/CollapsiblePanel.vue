<script setup lang="ts">
import { ref } from "vue";

const props = withDefaults(
  defineProps<{
    title: string;
    meta?: string | number | null;
    panelClass?: string;
    defaultOpen?: boolean;
  }>(),
  {
    meta: null,
    panelClass: "",
    defaultOpen: false,
  },
);

const isOpen = ref(props.defaultOpen);
</script>

<template>
  <section :class="['panel', 'collapsible-panel', panelClass]">
    <button
      class="collapsible-trigger"
      type="button"
      :aria-expanded="isOpen"
      @click="isOpen = !isOpen"
    >
      <span>{{ title }}</span>
      <span class="collapsible-meta">
        <small v-if="meta !== null">{{ meta }}</small>
        <span :class="['chevron', { open: isOpen }]" aria-hidden="true"></span>
      </span>
    </button>
    <div v-if="isOpen" class="collapsible-body">
      <slot />
    </div>
  </section>
</template>
