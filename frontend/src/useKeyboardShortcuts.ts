import { onMounted, onUnmounted } from "vue";

export interface KeyboardShortcut {
  key: string;
  ctrlOrMeta?: boolean;
  shift?: boolean;
  allowEditableTarget?: boolean;
  preventDefault?: boolean;
  ignoreRepeat?: boolean;
  handler: (event: KeyboardEvent) => void;
}

function isEditableTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  return Boolean(
    target.closest("input, select, textarea, button") || target.isContentEditable,
  );
}

function normalizedKey(event: KeyboardEvent) {
  if (event.key === " ") {
    return "space";
  }
  if (event.key.length === 1) {
    return event.key.toLowerCase();
  }
  return event.key.toLowerCase();
}

function matchesShortcut(event: KeyboardEvent, shortcut: KeyboardShortcut) {
  if (normalizedKey(event) !== shortcut.key.toLowerCase()) {
    return false;
  }
  if (Boolean(shortcut.ctrlOrMeta) !== (event.ctrlKey || event.metaKey)) {
    return false;
  }
  if (shortcut.shift !== undefined && shortcut.shift !== event.shiftKey) {
    return false;
  }
  return true;
}

export function useKeyboardShortcuts(shortcuts: () => KeyboardShortcut[]) {
  function onKeydown(event: KeyboardEvent) {
    for (const shortcut of shortcuts()) {
      if (!matchesShortcut(event, shortcut)) {
        continue;
      }
      if (shortcut.ignoreRepeat !== false && event.repeat) {
        return;
      }
      if (!shortcut.allowEditableTarget && isEditableTarget(event.target)) {
        return;
      }
      if (shortcut.preventDefault !== false) {
        event.preventDefault();
      }
      shortcut.handler(event);
      return;
    }
  }

  onMounted(() => {
    window.addEventListener("keydown", onKeydown);
  });

  onUnmounted(() => {
    window.removeEventListener("keydown", onKeydown);
  });
}
