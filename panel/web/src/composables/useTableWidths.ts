import { computed, ref } from "vue";

/** 列宽按表名存 localStorage：刷新后保留用户手动拖过的宽度。 */
const STORAGE_KEY = "panel-table-widths";

type WidthMap = Record<string, Record<string, number>>;

function read(): WidthMap {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") return {};
    return parsed as WidthMap;
  } catch {
    return {};
  }
}

const all = ref<WidthMap>(read());

export function useTableWidths(name: string) {
  const widths = computed(() => all.value[name] ?? {});

  /** 该列被拖动过就返回固定宽度，否则交给 `min-width` 按比例分配。 */
  function widthFor(label: string): number | undefined {
    return widths.value[label];
  }

  function onHeaderDragEnd(newWidth: number, _oldWidth: number, column: { label?: string }) {
    const label = column?.label;
    if (!label || !Number.isFinite(newWidth)) return;
    all.value = {
      ...all.value,
      [name]: { ...widths.value, [label]: Math.round(newWidth) },
    };
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(all.value));
    } catch {
      /* 隐私模式下写不进去就算了，不阻断拖动 */
    }
  }

  function reset() {
    const next = { ...all.value };
    delete next[name];
    all.value = next;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      /* 同上 */
    }
  }

  return { widthFor, onHeaderDragEnd, reset };
}
