import { ref } from "vue";

export type FontSize = "sm" | "md" | "lg";

const STORAGE_KEY = "panel-font-size";
const fontSize = ref<FontSize>("md");

function apply(value: FontSize) {
  fontSize.value = value;
  document.documentElement.dataset.fontSize = value;
  try {
    localStorage.setItem(STORAGE_KEY, value);
  } catch {
    /* 隐私模式忽略 */
  }
}

export function initUiSettings(): void {
  let stored: FontSize = "md";
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "sm" || saved === "md" || saved === "lg") stored = saved;
  } catch {
    /* ignore */
  }
  apply(stored);
}

export function useUiSettings() {
  return {
    fontSize,
    setFontSize: apply,
    reset: () => apply("md"),
  };
}
