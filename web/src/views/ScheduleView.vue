<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { onBeforeRouteLeave } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";

import { get, post } from "../api";
import ErrorState from "../components/ErrorState.vue";
import PageHeader from "../components/PageHeader.vue";
import SaveResultPanel from "../components/SaveResultPanel.vue";
import StatusPill from "../components/StatusPill.vue";
import { useConfigStore } from "../stores/config";
import type { SchedulePreview } from "../types";
import { formatTime } from "../utils/format";

const store = useConfigStore();
const cron = ref("");
const serverCron = ref("");
const timezone = ref("");
const preview = ref<string[]>([]);
const previewError = ref("");
const loadError = ref("");
const applyResult = ref("");
const applying = ref(false);

const templates = [
  { label: "每 6 小时", value: "30 */6 * * *" },
  { label: "每天 03:00", value: "0 3 * * *" },
  { label: "每 2 小时", value: "0 */2 * * *" },
  { label: "每 30 分钟", value: "*/30 * * * *" },
];

const dirty = computed(() => cron.value !== serverCron.value);

async function loadPreview() {
  previewError.value = "";
  try {
    const data = await get<SchedulePreview>(
      `/api/schedule/preview?cron=${encodeURIComponent(cron.value)}`,
    );
    timezone.value = data.tz;
    preview.value = data.runs;
  } catch (error) {
    previewError.value = (error as Error).message;
    preview.value = [];
  }
}

async function load() {
  loadError.value = "";
  try {
    await store.load();
    const param = store.params.find((item) => item.name === "CRON_SCHEDULE");
    serverCron.value = param ? String(param.value) : "";
    cron.value = serverCron.value;
    await loadPreview();
  } catch (error) {
    loadError.value = (error as Error).message;
  }
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
    await loadPreview();
  } catch (error) {
    ElMessage.error((error as Error).message);
  }
}

async function applyNow() {
  applying.value = true;
  applyResult.value = "";
  try {
    const data = await post<{ applied: boolean; output: string }>("/api/schedule/apply");
    applyResult.value = data.output ? `已应用\n${data.output}` : "已应用";
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
  void loadPreview();
}

async function verifyNow() {
  try {
    await store.verify();
    ElMessage.success("已重新核对");
  } catch (error) {
    ElMessage.error((error as Error).message);
  }
}

async function runNow() {
  try {
    await post("/api/runs");
    ElMessage.success("已触发一轮，可在「运行」页查看输出");
  } catch (error) {
    ElMessage.error((error as Error).message);
  }
}

async function restartScanner() {
  try {
    await post("/api/system/restart", undefined, { "X-Confirm": "restart" });
    ElMessage.success("已请求重启扫描容器");
  } catch (error) {
    ElMessage.error((error as Error).message);
  }
}

watch(cron, () => void loadPreview());
onMounted(load);

onBeforeRouteLeave(async () => {
  if (!dirty.value) return true;
  try {
    await ElMessageBox.confirm("有未保存的调度修改，确定离开？", "未保存的修改", {
      confirmButtonText: "离开",
      cancelButtonText: "留下",
      type: "warning",
    });
    return true;
  } catch {
    return false;
  }
});
</script>

<template>
  <section class="page page--flush">
    <PageHeader title="调度" subtitle="cron 表达式保存后热重载，无需重启容器">
      <el-button :loading="applying" @click="applyNow">重新应用调度</el-button>
    </PageHeader>

    <ErrorState v-if="loadError" :message="loadError" @retry="load" />

    <template v-else>
      <div class="grid schedule-grid">
        <section class="panel">
          <header class="panel__head">
            <span>CRON_SCHEDULE</span>
            <StatusPill tone="neutral" :label="timezone || '时区读取中'" />
          </header>
          <div class="panel__body stack">
            <el-input v-model="cron" class="mono" placeholder="例如 30 */6 * * *" />
            <div class="row">
              <el-button
                v-for="template in templates"
                :key="template.value"
                size="small"
                @click="cron = template.value"
              >
                {{ template.label }}
              </el-button>
            </div>
            <p class="muted hint">
              支持 5 段（分 时 日 月 周）、6 段（第 6 位是年）、7 段（含秒）；不支持 @daily 宏。
            </p>
          </div>
        </section>

        <section class="panel">
          <header class="panel__head">未来 5 次执行</header>
          <div class="panel__body">
            <p v-if="previewError" class="preview-error" role="alert">{{ previewError }}</p>
            <ol v-else-if="preview.length" class="preview-list">
              <li v-for="run in preview" :key="run" class="mono">{{ formatTime(run) }}</li>
            </ol>
            <p v-else class="muted">尚无预览；检查表达式是否合法。</p>
          </div>
        </section>
      </div>

      <pre v-if="applyResult" class="apply-output mono">{{ applyResult }}</pre>

      <SaveResultPanel
        :result="store.lastResult"
        @close="store.lastResult = null"
        @restart="restartScanner"
        @verify="verifyNow"
        @run="runNow"
      />

      <div class="actionbar">
        <span class="muted">{{ dirty ? "有未保存的调度修改" : "与已保存值一致" }}</span>
        <div class="actionbar__buttons">
          <el-button :disabled="!dirty" @click="cancel">取消</el-button>
          <el-button
            type="primary"
            :disabled="!dirty || Boolean(previewError)"
            :loading="store.saving"
            @click="save"
          >
            保存
          </el-button>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.schedule-grid {
  grid-template-columns: minmax(320px, 1.2fr) minmax(280px, 1fr);
}

.hint {
  margin: 0;
  font-size: 12px;
  line-height: 18px;
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
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 12px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 200px;
  overflow: auto;
}

@media (max-width: 1023px) {
  .schedule-grid {
    grid-template-columns: 1fr;
  }
}
</style>
