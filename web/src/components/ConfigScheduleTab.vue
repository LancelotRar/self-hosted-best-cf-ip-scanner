<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { RefreshRight, Timer } from "@element-plus/icons-vue";

import { get, post } from "../api";
import ParamField from "./ParamField.vue";
import { useConfigStore } from "../stores/config";
import type { Param, SchedulePreview } from "../types";
import { formatTime } from "../utils/format";

const store = useConfigStore();
const preview = ref<string[]>([]);
const timezone = ref("");
const previewError = ref("");
const applying = ref(false);
const applyOutput = ref("");

const params = computed<Param[]>(() =>
  store.params.filter((param) => param.group === "定时计划"),
);
const cronValue = computed(() => String(store.values.CRON_SCHEDULE ?? ""));

function update(param: Param, value: unknown) {
  store.applyLocal({ [param.name]: value });
}

async function loadPreview() {
  if (!cronValue.value.trim()) return;
  previewError.value = "";
  try {
    const data = await get<SchedulePreview>(
      `/api/schedule/preview?cron=${encodeURIComponent(cronValue.value)}`,
    );
    timezone.value = data.tz;
    preview.value = data.runs;
  } catch (error) {
    previewError.value = (error as Error).message;
    preview.value = [];
  }
}

async function applyNow() {
  applying.value = true;
  applyOutput.value = "";
  try {
    const data = await post<{ applied: boolean; output: string }>("/api/schedule/apply");
    applyOutput.value = data.output ? `已应用\n${data.output}` : "已应用";
    ElMessage.success("已应用调度");
  } catch (error) {
    applyOutput.value = `应用失败：${(error as Error).message}`;
    ElMessage.error((error as Error).message);
  } finally {
    applying.value = false;
  }
}

watch(cronValue, () => void loadPreview(), { immediate: true });
</script>

<template>
  <section class="block">
    <header class="block__head">
      <el-icon><Timer /></el-icon><span>调度与预览</span>
    </header>
    <div class="panel block__card">
      <ParamField
        v-for="param in params"
        :key="param.name"
        :param="param"
        :model-value="store.values[param.name]"
        @update:model-value="update(param, $event)"
      />

      <div class="schedule-preview">
        <div class="schedule-preview__head">
          <span class="row">
            <el-icon><Timer /></el-icon>
            <strong>未来 5 次执行</strong>
            <span v-if="timezone" class="muted">{{ timezone }}</span>
          </span>
          <el-button :loading="applying" size="small" @click="applyNow">
            <el-icon><RefreshRight /></el-icon>
            立即应用调度
          </el-button>
        </div>

        <p v-if="previewError" class="preview-error" role="alert">{{ previewError }}</p>
        <ol v-else-if="preview.length" class="preview-list">
          <li v-for="run in preview" :key="run" class="mono">{{ formatTime(run) }}</li>
        </ol>
        <p v-else class="muted">尚无预览；检查表达式是否合法。</p>

        <pre v-if="applyOutput" class="apply-output mono">{{ applyOutput }}</pre>
        <p class="muted schedule-note">
          「立即应用调度」只对已保存的 .env 生效；修改 cron 后请先保存。
        </p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.schedule-preview {
  margin-top: var(--space-3);
  padding: var(--space-4);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
}

.schedule-preview__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-bottom: var(--space-3);
}

.preview-list {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.preview-error {
  margin: 0;
  color: var(--danger);
  font-size: 13px;
  overflow-wrap: anywhere;
}

.apply-output {
  margin: var(--space-3) 0 0;
  padding: var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--surface);
  border: 1px solid var(--border);
  font-size: 12px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 180px;
  overflow: auto;
}

.schedule-note {
  margin: var(--space-2) 0 0;
  font-size: 12px;
}
</style>
