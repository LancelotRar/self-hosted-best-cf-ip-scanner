<script setup lang="ts">
import { computed, reactive, watch } from "vue";

import HintIcon from "./HintIcon.vue";
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
        <div class="name-field">
          <span class="name-label">
            <label for="artifact-detail">明细表</label>
            <HintIcon content="默认 detail.csv（不含扩展名）" label="查看「明细表」说明" />
          </span>
          <el-input
            id="artifact-detail"
            :model-value="detailName"
            maxlength="64"
            placeholder="detail"
            @update:model-value="setDetail"
          />
        </div>

        <div class="name-field">
          <span class="name-label">
            <label for="artifact-pinned">固定保留</label>
            <HintIcon content="默认 PINNED.txt（不含扩展名）" label="查看「固定保留」说明" />
          </span>
          <el-input
            id="artifact-pinned"
            :model-value="pinnedName"
            maxlength="64"
            placeholder="PINNED"
            @update:model-value="setPinned"
          />
        </div>
      </div>
    </section>

    <section class="names__group">
      <h3 class="names__title">全量列表</h3>
      <div v-if="fullTargets.length" class="name-grid">
        <div v-for="target in fullTargets" :key="target.key" class="name-field">
          <span class="name-label">
            <label :for="`artifact-${target.key}`">{{ target.label }}</label>
            <HintIcon
              :content="`默认 ${target.defaultStem}.txt`"
              :label="`查看「${target.label}」说明`"
            />
          </span>
          <el-input
            :id="`artifact-${target.key}`"
            :model-value="drafts[target.key] ?? target.defaultStem"
            maxlength="64"
            @update:model-value="(value: string) => setListName(target, value)"
          />
        </div>
      </div>
      <p v-else class="muted names__empty">当前没有配置全量列表档位。</p>
    </section>

    <section v-if="countryTargets.length" class="names__group">
      <h3 class="names__title">国家列表</h3>
      <div class="name-grid">
        <div v-for="target in countryTargets" :key="target.key" class="name-field">
          <span class="name-label">
            <label :for="`artifact-${target.key}`">{{ target.label }}</label>
            <HintIcon
              :content="`默认 ${target.defaultStem}.txt`"
              :label="`查看「${target.label}」说明`"
            />
          </span>
          <el-input
            :id="`artifact-${target.key}`"
            :model-value="drafts[target.key] ?? target.defaultStem"
            maxlength="64"
            @update:model-value="(value: string) => setListName(target, value)"
          />
        </div>
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
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  column-gap: 24px;
  row-gap: 20px;
}

.name-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.name-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--text);
  font-size: var(--fs-label);
  font-weight: 600;
  line-height: 20px;
}

.names__empty {
  margin: 0;
  font-size: var(--fs-meta);
}
</style>
