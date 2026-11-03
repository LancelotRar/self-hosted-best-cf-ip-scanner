<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";

import { get, post } from "../api";
import { useConfigStore } from "../stores/config";
import type { SchedulePreview } from "../types";

const store = useConfigStore();
const cron = ref("");
const serverCron = ref("");
const tz = ref("");
const runs = ref<string[]>([]);
const previewError = ref("");
const applyResult = ref("");
const applying = ref(false);

const templates = [
  { label: "每 6 小时", value: "30 */6 * * *" },
  { label: "每天 03:00", value: "0 3 * * *" },
  { label: "每 2 小时", value: "0 */2 * * *" },
  { label: "每 30 分钟", value: "*/30 * * * *" },
];

const dirty = computed(() => cron.value !== serverCron.value);

async function preview() {
  previewError.value = "";
  try {
    const data = await get<SchedulePreview>(
      `/api/schedule/preview?cron=${encodeURIComponent(cron.value)}`,
    );
    tz.value = data.tz;
    runs.value = data.runs;
  } catch (error) {
    previewError.value = (error as Error).message;
    runs.value = [];
  }
}

async function load() {
  await store.load();
  const param = store.params.find((item) => item.name === "CRON_SCHEDULE");
  serverCron.value = param ? String(param.value) : "";
  cron.value = serverCron.value;
  await preview();
}

async function save() {
  store.applyLocal({ CRON_SCHEDULE: cron.value });
  try {
    const result = await store.save();
    serverCron.value = cron.value;
    applyResult.value = result?.effects.schedule_reloaded
      ? "已热重载调度"
      : "已保存；调度未变化或扫描容器离线（watcher 会补应用）";
    ElMessage.success("已保存");
    await preview();
  } catch (error) {
    ElMessage.error((error as Error).message);
  }
}

async function applyNow() {
  applying.value = true;
  applyResult.value = "";
  try {
    await post("/api/schedule/apply");
    applyResult.value = "已重新应用调度";
    ElMessage.success("已应用");
  } catch (error) {
    applyResult.value = `应用失败：${(error as Error).message}`;
    ElMessage.error((error as Error).message);
  } finally {
    applying.value = false;
  }
}

function cancel() {
  cron.value = serverCron.value;
  void preview();
}

function formatTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false });
}

watch(cron, () => void preview());
onMounted(load);
</script>

<template>
  <section class="panel-page">
    <div class="panel-page__title">
      <h1>调度</h1>
      <el-button :loading="applying" @click="applyNow">重新应用调度</el-button>
    </div>

    <el-alert v-if="applyResult" :title="applyResult" type="info" :closable="false" show-icon />

    <el-card shadow="never" class="block">
      <template #header>CRON_SCHEDULE（{{ tz || "时区读取中" }}）</template>
      <el-input v-model="cron" placeholder="例如 30 */6 * * *" />
      <div class="templates">
        <el-button
          v-for="template in templates"
          :key="template.value"
          size="small"
          @click="cron = template.value"
        >
          {{ template.label }}
        </el-button>
      </div>
      <p class="panel-muted">支持 5 段（分 时 日 月 周）与 6 段（秒 分 时 日 月 周），不支持 @daily。</p>
    </el-card>

    <el-card shadow="never" class="block">
      <template #header>未来 5 次执行</template>
      <el-alert v-if="previewError" :title="previewError" type="error" :closable="false" show-icon />
      <ol v-else-if="runs.length">
        <li v-for="run in runs" :key="run">{{ formatTime(run) }}</li>
      </ol>
      <el-empty v-else description="尚无预览；检查表达式是否合法" />
    </el-card>

    <div class="actionbar">
      <span class="panel-muted">{{ dirty ? "有未保存的调度修改" : "与已保存值一致" }}</span>
      <div>
        <el-button :disabled="!dirty" @click="cancel">取消</el-button>
        <el-button type="primary" :disabled="!dirty || Boolean(previewError)" :loading="store.saving" @click="save">
          保存
        </el-button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.block {
  margin-top: 16px;
}

.templates {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.actionbar {
  position: sticky;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  margin-top: 16px;
  background: var(--panel-surface);
  border: 1px solid var(--panel-border);
  border-radius: 8px;
}

ol {
  margin: 0;
  padding-left: 20px;
}
</style>
