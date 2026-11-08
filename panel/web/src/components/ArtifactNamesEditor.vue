<script setup lang="ts">
import { computed, reactive, watch } from "vue";

import { useConfigStore } from "../stores/config";

interface Target {
  key: string;
  label: string;
  defaultStem: string;
}

const store = useConfigStore();
const drafts = reactive<Record<string, string>>({});

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
      defaultStem: `GLOBAL${count}`,
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
        defaultStem: `${code}${count}`,
      };
    })
    .filter((target): target is Target => Boolean(target));
});

const allTargets = computed(() => [...fullTargets.value, ...countryTargets.value]);

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

const detailName = computed(() => String(store.values.DETAIL_CSV_NAME ?? "detail"));
const pinnedName = computed(() => String(store.values.PINNED_OUTPUT_NAME ?? "PINNED"));

function syncDrafts() {
  for (const target of allTargets.value) {
    drafts[target.key] = mapping.value[target.key] ?? target.defaultStem;
  }
}

watch(allTargets, syncDrafts, { immediate: true });
watch(() => store.serverValues, syncDrafts, { deep: true });
watch(
  () => store.dirty,
  (dirty) => {
    if (!dirty) syncDrafts();
  },
);

function setDetail(value: string) {
  store.applyLocal({ DETAIL_CSV_NAME: value });
}

function setPinned(value: string) {
  store.applyLocal({ PINNED_OUTPUT_NAME: value });
}

function setListName(target: Target, value: string) {
  drafts[target.key] = value;
  const next = { ...mapping.value };
  const trimmed = value.trim();
  if (!trimmed || trimmed === target.defaultStem) {
    delete next[target.key];
  } else {
    next[target.key] = trimmed;
  }
  store.applyLocal({
    LIST_FILENAMES: Object.keys(next).length ? JSON.stringify(next) : "",
  });
}
</script>

<template>
  <div class="names">
    <section class="names__group">
      <h3 class="names__title">基础文件</h3>
      <div class="name-grid">
        <label class="name-field">
          <span class="name-label">明细表</span>
          <el-input
            :model-value="detailName"
            maxlength="64"
            placeholder="detail"
            @update:model-value="setDetail"
          />
          <span class="name-hint">默认 detail.csv（不含扩展名）</span>
        </label>

        <label class="name-field">
          <span class="name-label">固定保留</span>
          <el-input
            :model-value="pinnedName"
            maxlength="64"
            placeholder="PINNED"
            @update:model-value="setPinned"
          />
          <span class="name-hint">默认 PINNED.txt（不含扩展名）</span>
        </label>
      </div>
    </section>

    <section class="names__group">
      <h3 class="names__title">全量列表</h3>
      <div v-if="fullTargets.length" class="name-grid">
        <label v-for="target in fullTargets" :key="target.key" class="name-field">
          <span class="name-label">{{ target.label }}</span>
          <el-input
            :model-value="drafts[target.key] ?? target.defaultStem"
            maxlength="64"
            @update:model-value="(value: string) => setListName(target, value)"
          />
          <span class="name-hint">默认 {{ target.defaultStem }}.txt</span>
        </label>
      </div>
      <p v-else class="muted names__empty">当前没有配置全量列表档位。</p>
    </section>

    <section v-if="countryTargets.length" class="names__group">
      <h3 class="names__title">国家列表</h3>
      <div class="name-grid">
        <label v-for="target in countryTargets" :key="target.key" class="name-field">
          <span class="name-label">{{ target.label }}</span>
          <el-input
            :model-value="drafts[target.key] ?? target.defaultStem"
            maxlength="64"
            @update:model-value="(value: string) => setListName(target, value)"
          />
          <span class="name-hint">默认 {{ target.defaultStem }}.txt</span>
        </label>
      </div>
    </section>
  </div>
</template>

<style scoped>
.names {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.names__group {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.names__title {
  margin: 0;
  color: var(--text);
  font-size: var(--fs-label);
  font-weight: 600;
  line-height: 20px;
}

.name-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 32px;
  row-gap: 20px;
}

.name-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.name-label {
  color: var(--text);
  font-size: var(--fs-label);
  font-weight: 600;
  line-height: 20px;
}

.name-hint {
  color: var(--text-muted);
  font-size: var(--fs-meta);
  line-height: 18px;
}

.names__empty {
  margin: 0;
  font-size: var(--fs-meta);
}

@media (max-width: 1023px) {
  .name-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
