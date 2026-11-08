<script setup lang="ts">
import { computed } from "vue";

import { useConfigStore } from "../stores/config";

interface Target {
  key: string;
  label: string;
  filename: string;
}

const store = useConfigStore();

const mapping = computed<Record<string, string>>(() => {
  const raw = store.values.LIST_FILENAMES;
  if (!raw) return {};
  try {
    const data = JSON.parse(String(raw)) as unknown;
    return data && typeof data === "object" && !Array.isArray(data)
      ? (data as Record<string, string>)
      : {};
  } catch {
    return {};
  }
});

function filenameOf(key: string): string {
  const stem = mapping.value[key] ?? key;
  return /\.txt$/i.test(stem) ? stem : `${stem}.txt`;
}

const fullTargets = computed<Target[]>(() => {
  if (!store.values.OVERALL_ENABLED) return [];
  const value = store.values.OVERALL_TOPS;
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => Number(item))
    .filter((item) => Number.isFinite(item) && item > 0)
    .map((count) => ({
      key: `GLOBAL${count}`,
      label: `全量 ${count} 条`,
      filename: filenameOf(`GLOBAL${count}`),
    }));
});

const countryTargets = computed<Target[]>(() => {
  if (!store.values.COUNTRY_FILTERS) return [];
  return store.params
    .filter((param) => param.name.startsWith("TOP_"))
    .map((param) => {
      const count = Number(store.values[param.name] ?? 0);
      if (!Number.isFinite(count) || count <= 0) return null;
      const code = param.name.slice(4);
      return {
        key: `${code}${count}`,
        label: `${code} · ${count} 条`,
        filename: filenameOf(`${code}${count}`),
      };
    })
    .filter((target): target is Target => Boolean(target));
});

const targets = computed(() => [...fullTargets.value, ...countryTargets.value]);

/** null = 默认全部推送；Set = 只推送选中项。 */
const selected = computed<Set<string> | null>(() => {
  const raw = store.values.PUSH_LISTS;
  if (!raw) return null;
  try {
    const data = JSON.parse(String(raw)) as unknown;
    return Array.isArray(data) ? new Set(data.filter((item) => typeof item === "string")) : null;
  } catch {
    return null;
  }
});

const selectedCount = computed(() =>
  selected.value === null ? targets.value.length : targets.value.filter((t) => selected.value?.has(t.key)).length,
);

function isOn(key: string): boolean {
  return selected.value === null || selected.value.has(key);
}

function toggle(key: string, on: boolean) {
  const allKeys = targets.value.map((target) => target.key);
  const next = selected.value ? new Set(selected.value) : new Set(allKeys);
  if (on) next.add(key);
  else next.delete(key);
  if (allKeys.every((item) => next.has(item))) {
    store.applyLocal({ PUSH_LISTS: "" });
  } else {
    store.applyLocal({ PUSH_LISTS: JSON.stringify(allKeys.filter((item) => next.has(item))) });
  }
}
</script>

<template>
  <div class="push-list">
    <p class="push-list__meta">
      已选择 {{ selectedCount }} / {{ targets.length }} 个列表
    </p>

    <div v-if="targets.length" class="push-list__rows">
      <div v-for="target in targets" :key="target.key" class="push-row">
        <div class="push-row__text">
          <span class="push-row__label">{{ target.label }}</span>
          <span class="push-row__file mono">{{ target.filename }}</span>
        </div>
        <el-switch
          :model-value="isOn(target.key)"
          :aria-label="`推送 ${target.filename}`"
          @change="(value: string | number | boolean) => toggle(target.key, Boolean(value))"
        />
      </div>
    </div>
    <p v-else class="muted push-list__empty">当前没有可推送的全量或国家列表。</p>
  </div>
</template>

<style scoped>
.push-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.push-list__meta {
  margin: 0;
  color: var(--text-muted);
  font-size: 12px;
}

.push-list__rows {
  display: flex;
  flex-direction: column;
}

.push-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: 10px 0;
}

.push-row + .push-row {
  border-top: 1px solid var(--border-soft);
}

.push-row__text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.push-row__label {
  color: var(--text);
  font-size: 13px;
  font-weight: 600;
  line-height: 20px;
}

.push-row__file {
  color: var(--text-muted);
  font-size: 12px;
  line-height: 18px;
  overflow-wrap: anywhere;
}

.push-list__empty {
  margin: 0;
  font-size: 12px;
}
</style>
