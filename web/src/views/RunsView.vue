<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";

import { get, post } from "../api";
import EmptyState from "../components/EmptyState.vue";
import ErrorState from "../components/ErrorState.vue";
import LogConsole from "../components/LogConsole.vue";
import PageHeader from "../components/PageHeader.vue";
import StatusPill from "../components/StatusPill.vue";
import { useEventStream } from "../composables/useEventStream";
import type { RunRecord } from "../types";
import { exitLabel, formatDuration, formatTime } from "../utils/format";

const router = useRouter();
const activeTab = ref("run");
const ended = ref(false);
const runId = ref("");
const lines = ref<string[]>([]);
const error = ref("");
const history = ref<RunRecord[]>([]);
const loading = ref(false);
const triggering = ref(false);

const { status, lastReceived, connect } = useEventStream(
  () => (runId.value ? `/api/runs/${encodeURIComponent(runId.value)}/stream` : "/api/runs/pending/stream"),
  {
    onMessage: (data) => lines.value.push(data),
    onDone: (code) => {
      ended.value = true;
      lines.value.push(`[结束] 退出码 ${code}`);
      ElMessage.info(`本轮结束，退出码 ${code}`);
      void loadHistory();
    },
    onError: (message) => lines.value.push(`[${message}]`),
    retryOnError: false,
  },
);

const running = ref(false);

function runTone(record: RunRecord): "success" | "warning" | "info" | "neutral" {
  if (record.status === "running") return "info";
  if (record.status === "interrupted") return "warning";
  if (record.status === "done") return "success";
  return "neutral";
}

function runLabel(record: RunRecord): string {
  if (record.status === "running") return "运行中";
  if (record.status === "interrupted") return "中断";
  if (record.status === "done") return "完成";
  return "—";
}

async function loadHistory() {
  loading.value = true;
  try {
    const data = await get<{ runs: RunRecord[] }>("/api/runs");
    history.value = data.runs;
    running.value = data.runs.some((record) => record.status === "running");
  } catch (exception) {
    error.value = (exception as Error).message;
  } finally {
    loading.value = false;
  }
}

async function trigger() {
  error.value = "";
  triggering.value = true;
  try {
    const data = await post<{ run_id: string }>("/api/runs");
    runId.value = data.run_id;
    lines.value = [];
    ended.value = false;
    running.value = true;
    connect();
    activeTab.value = "run";
  } catch (exception) {
    error.value = (exception as Error).message;
    ElMessage.error((exception as Error).message);
  } finally {
    triggering.value = false;
  }
}

onMounted(async () => {
  await loadHistory();
  const live = history.value.find(
    (record) => record.status === "running" && record.trigger === "panel",
  );
  if (live) {
    runId.value = live.run_id;
    lines.value = [`[已接上进行中的轮次 ${live.run_id}]`];
    connect();
  }
});
</script>

<template>
  <section class="page">
    <PageHeader title="运行" subtitle="手动执行与定时任务共用同一份 .env，仅触发方式不同">
      <el-button type="primary" :loading="triggering" :disabled="running" @click="trigger">
        立即执行一轮
      </el-button>
    </PageHeader>

    <ErrorState v-if="error" :message="error" @retry="loadHistory" />

    <el-tabs v-model="activeTab">
      <el-tab-pane label="立即运行" name="run">
        <div class="run-head">
          <StatusPill
            :tone="running ? 'info' : 'neutral'"
            :label="running ? '有轮次在运行' : '当前空闲'"
            :pulse="running"
          />
          <span class="muted">
            同一时间只允许一轮；定时任务正在跑时手动触发会被拒绝（409）。
          </span>
        </div>
        <LogConsole
          v-if="runId"
          :lines="lines"
          :status="status"
          :last-received="lastReceived"
          :ended="ended"
        />
        <EmptyState
          v-else
          :title="running ? '定时任务正在执行' : '尚无运行输出'"
          :description="
            running
              ? '定时轮次的输出请到「日志」页查看；手动执行时会在这里实时显示。'
              : '点击右上角「立即执行一轮」开始；执行期间可实时查看输出。'
          "
          :action-label="running ? '去日志页' : ''"
          @action="router.push({ name: 'logs' })"
        />
      </el-tab-pane>

      <el-tab-pane label="历史轮次" name="history">
        <div class="toolbar">
          <el-button :loading="loading" @click="loadHistory">刷新</el-button>
        </div>
        <el-table v-if="history.length" :data="history" size="small">
          <el-table-column label="轮次" min-width="180">
            <template #default="{ row }"><span class="mono">{{ row.run_id }}</span></template>
          </el-table-column>
          <el-table-column label="触发" width="80">
            <template #default="{ row }">{{ row.trigger ?? "—" }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <StatusPill :tone="runTone(row)" :label="runLabel(row)" />
            </template>
          </el-table-column>
          <el-table-column label="扫描" width="110">
            <template #default="{ row }">{{ exitLabel(row.scan_exit) }}</template>
          </el-table-column>
          <el-table-column label="发布" width="110">
            <template #default="{ row }">{{ exitLabel(row.publish_exit) }}</template>
          </el-table-column>
          <el-table-column label="耗时" width="90">
            <template #default="{ row }">{{ formatDuration(row.duration_s) }}</template>
          </el-table-column>
          <el-table-column label="开始" min-width="170">
            <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
          </el-table-column>
          <el-table-column label="摘要" min-width="160">
            <template #default="{ row }">
              <span class="muted">{{ row.summary ?? "—" }}</span>
            </template>
          </el-table-column>
        </el-table>
        <EmptyState
          v-else
          title="尚无轮次记录"
          description="定时任务或手动执行完成后出现在这里"
          action-label="刷新"
          @action="loadHistory"
        />
      </el-tab-pane>
    </el-tabs>
  </section>
</template>

<style scoped>
.run-head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-bottom: var(--space-3);
  font-size: 12px;
}
</style>
