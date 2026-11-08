<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Clock, Timer } from "@element-plus/icons-vue";

import { get } from "../api";
import { useConfigStore } from "../stores/config";
import type { SchedulePreview } from "../types";
import { formatMinute } from "../utils/format";

const store = useConfigStore();
const preview = ref<string[]>([]);
const timezone = ref("");
const previewError = ref("");
const previewing = ref(false);
const saveError = ref("");

const presets = [
  { label: "每 1 小时", value: "0 * * * *" },
  { label: "每 3 小时 30 分", value: "30 */3 * * *" },
  { label: "每天 0:00", value: "0 0 * * *" },
  { label: "每天 12:45", value: "45 12 * * *" },
  { label: "每周一 6:30", value: "30 6 * * 1" },
];

const cronValue = computed({
  get: () => String(store.values.CRON_SCHEDULE ?? ""),
  set: (value: string) => store.applyLocal({ CRON_SCHEDULE: value }),
});

const previewRows = computed(() =>
  preview.value.map((run) => {
    const [date, time] = formatMinute(run).split(" ");
    return { date, time };
  }),
);

function usePreset(value: string) {
  cronValue.value = value;
}

async function loadPreview() {
  if (!cronValue.value.trim()) return;
  previewError.value = "";
  previewing.value = true;
  try {
    const data = await get<SchedulePreview>(
      `/api/schedule/preview?cron=${encodeURIComponent(cronValue.value)}`,
    );
    timezone.value = data.tz;
    preview.value = data.runs;
  } catch (error) {
    previewError.value = (error as Error).message;
    preview.value = [];
  } finally {
    previewing.value = false;
  }
}

function cancel() {
  store.cancel();
  saveError.value = "";
}

async function saveSchedule() {
  saveError.value = "";
  try {
    const result = await store.save();
    ElMessage.success(
      result?.effects.schedule_reloaded ? "计划任务已保存并生效" : "计划任务已保存",
    );
  } catch (error) {
    const failure = error as Error & { status?: number };
    if (failure.status === 409) {
      try {
        await ElMessageBox.confirm(
          "设置已被其他方式修改。重新加载会丢弃当前未保存的修改。",
          "设置已被修改",
          { confirmButtonText: "重新加载", cancelButtonText: "取消", type: "warning" },
        );
        await store.load();
      } catch {
        /* 用户取消 */
      }
      return;
    }
    saveError.value = failure.message;
  }
}

// 直接打开 `?tab=schedule` 时，组件可能先于配置加载完成挂载；
// 同时观察 loading，确保配置到位后再计算一次预览。
watch(
  () => [cronValue.value, store.loading] as const,
  ([cron, loading]) => {
    if (!loading && cron.trim()) void loadPreview();
  },
  { immediate: true },
);
</script>

<template>
  <div class="schedule-grid">
    <section class="block">
      <header class="block__head">
        <el-icon><Timer /></el-icon><span>执行频率</span>
      </header>
      <div class="panel block__card schedule-card">
        <p class="schedule-help">选择常用节奏，或直接填写表达式。</p>

        <div class="preset-row" role="group" aria-label="常用执行频率">
          <el-button
            v-for="preset in presets"
            :key="preset.value"
            size="small"
            class="preset-button"
            :class="{ 'preset-button--active': cronValue === preset.value }"
            @click="usePreset(preset.value)"
          >
            {{ preset.label }}
          </el-button>
        </div>

        <el-input
          id="param-CRON_SCHEDULE"
          v-model="cronValue"
          class="mono schedule-input"
          placeholder="30 */6 * * *"
        />
        <p v-if="previewError" class="preview-error" role="alert">{{ previewError }}</p>
        <p v-else class="schedule-help schedule-help--mono">
          5 段：分 时 日 月 周；6 段：再加年；7 段：秒 + 分 时 日 月 周 + 年。
        </p>

        <p v-if="saveError" class="preview-error" role="alert">{{ saveError }}</p>

        <div class="schedule-summary">
          <span class="muted">下一次运行</span>
          <strong class="mono">
            {{ previewRows[0] ? `${previewRows[0].date} ${previewRows[0].time}` : "—" }}
          </strong>
        </div>

        <footer class="schedule-actions">
          <span class="muted">
            {{ store.dirty ? `未保存 ${store.dirtyCount} 项` : "没有未保存的修改" }}
          </span>
          <span class="spacer" />
          <el-button :disabled="!store.dirty" @click="cancel">取消</el-button>
          <el-button
            type="primary"
            :disabled="!store.dirty || Boolean(previewError)"
            :loading="store.saving"
            @click="saveSchedule"
          >
            保存
          </el-button>
        </footer>
      </div>
    </section>

    <section class="block">
      <header class="block__head">
        <el-icon><Clock /></el-icon><span>未来 5 次执行计划</span>
      </header>
      <div class="panel block__card preview-card">
        <p class="preview-meta">
          <span v-if="timezone">
            <span class="muted">时区</span>
            <span class="mono preview-meta__value">{{ timezone }}</span>
          </span>
          <span class="muted">保存后自动应用</span>
        </p>

        <el-table
          v-if="previewRows.length"
          :data="previewRows"
          border
          size="small"
          class="preview-table"
        >
          <el-table-column label="日期" min-width="150">
            <template #default="{ row }"><span class="mono">{{ row.date }}</span></template>
          </el-table-column>
          <el-table-column label="时间" width="110" align="right">
            <template #default="{ row }"><span class="mono">{{ row.time }}</span></template>
          </el-table-column>
        </el-table>
        <p v-else-if="previewing" class="muted">正在计算下一次执行…</p>
        <p v-else class="muted">暂时无法预览，请检查表达式。</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.schedule-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-5);
  align-items: stretch;
}

.schedule-grid .block {
  min-width: 0;
}

.schedule-card,
.preview-card {
  display: flex;
  flex: 1;
  flex-direction: column;
}

.schedule-help {
  margin: 0;
  color: var(--text-muted);
  font-size: var(--fs-meta);
  line-height: 18px;
}

.schedule-help--mono {
  color: var(--text-faint);
}

.preset-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin: var(--space-4) 0;
}

.preset-button {
  height: 32px;
  padding: 0 12px;
  border-radius: var(--radius-sm);
  color: var(--text);
}

.preset-button--active {
  color: var(--on-primary);
  border-color: var(--primary);
  background: var(--primary);
}

.schedule-input {
  max-width: 420px;
  margin-bottom: var(--space-2);
}

.schedule-summary {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
  margin-top: auto;
  padding-top: var(--space-5);
  font-size: var(--fs-meta);
}

.schedule-summary strong {
  font-size: var(--fs-body);
  font-weight: 600;
}

.schedule-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-soft);
  font-size: var(--fs-meta);
}

.preview-card {
  gap: var(--space-3);
}

.preview-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin: 0;
  font-size: var(--fs-meta);
}

.preview-meta__value {
  margin-left: 4px;
  color: var(--text);
}

.preview-table {
  width: 100%;
}

.preview-error {
  margin: var(--space-2) 0 0;
  color: var(--danger);
  font-size: 13px;
  overflow-wrap: anywhere;
}

@media (max-width: 1023px) {
  .schedule-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
