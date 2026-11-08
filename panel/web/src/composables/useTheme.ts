import { ref } from "vue";

export type Theme = "dark" | "light";

const STORAGE_KEY = "panel-theme";
const theme = ref<Theme>("light");

function apply(next: Theme) {
  theme.value = next;
  document.documentElement.dataset.theme = next;
  try {
    localStorage.setItem(STORAGE_KEY, next);
  } catch {
    /* 隐私模式忽略 */
  }
}

export function initTheme(): void {
  let saved: Theme | null = null;
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "dark" || stored === "light") saved = stored;
  } catch {
    /* ignore */
  }
  apply(saved ?? "light");
}

export function useTheme() {
  return {
    theme,
    set: apply,
    toggle: () => apply(theme.value === "dark" ? "light" : "dark"),
  };
}
