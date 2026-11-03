<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import { get, post } from "../api";
import LogConsole from "../components/LogConsole.vue";
import { useEventStream } from "../composables/useEventStream";
import type { RunRecord } from "../types";

const activeTab = ref("run");
const runId = ref("");
const lines = ref<string[]>([]);
const error = ref("");
const history = ref<RunRecord[]>([]);
const loadingHistory = ref(false);

const { status, lastReceived, connect } = useEventStream(
  () => (runId.value ? `/api/runs/${encodeURIComponent(runId.value)}/stream` : "/api/runs/pending/stream"),
  {
    onMessage: (data) => lines.value.push(data),
    onDone: (code) => {
      lines.value.push(`[结束] 退出码 ${code}`);
      ElMessage.info(`本轮结束，退出码 ${code}`);
      void loadHistory();
    },
    onError: (message) => lines.value.push(`[${message}]`),
    retryOnError: false,
  },
);

async function loadHistory() {
  loadingHistory.value = true;
  try {
    const data = await get<{ runs: RunRecord[] }>("/api/runs");
    history.value = data.runs;
  } catch (exception) {
    error.value = (exception as Error).message;
  } finally {
    loadingHistory.value = false;
  }
}

async function trigger() {
  error.value = "";
  try {
    const data = await post<{ run_id: string }>("/api/runs");
    runId.value = data.run_id;
    lines.value = [];
    connect();
    activeTab.value = "run";
  } catch (exception) {
    error.value = (exception as Error).message;
    ElMessage.error((exception as Error).message);
  }
}

function exitTag(code: number | null): { type: "success" | "danger" | "info"; text: string } {
  if (code === null) return { type: "info", text: "—" };
  return code === 0 ? { type: "success", text: "成功" } : { type: "danger", text: `失败（${code}）` };
}

function formatTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false });
}

onMounted(async () => {
  await loadHistory();
  // 切回运行页时自动接上"面板触发且仍在跑"的那一轮（定时轮次无法回放 stdout）。
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
  <section class="panel-page">
    <div class="panel-page__title">
      <h1>运行</h1>
      <el-button type="primary" @click="trigger">立即执行一轮</el-button>
    </div>

    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />

    <el-tabs v-model="activeTab">
      <el-tab-pane label="立即运行" name="run">
        <LogConsole :lines="lines" :status="status" :last-received="lastReceived" />
        <p class="panel-muted">
          同一时间只允许一轮：若定时任务正在跑，触发会被拒绝（提示"已有一轮在运行"）。
        </p>
      </el-tab-pane>

      <el-tab-pane label="历史轮次" name="history">
        <el-button :loading="loadingHistory" @click="loadHistory">刷新</el-button>
        <el-table :data="history" size="small" class="table">
          <el-table-column prop="run_id" label="轮次" width="200" />
          <el-table-column prop="trigger" label="触发" width="90" />
          <el-table-column label="开始" width="180">
            <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
          </el-table-column>
          <el-table-column label="扫描" width="120">
            <template #default="{ row }">
              <el-tag :type="exitTag(row.scan_exit).type" size="small">{{ exitTag(row.scan_exit).text }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="发布" width="120">
            <template #default="{ row }">
              <el-tag :type="exitTag(row.publish_exit).type" size="small">{{ exitTag(row.publish_exit).text }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="duration_s" label="耗时(s)" width="100" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.status === 'running'" type="primary" size="small">运行中</el-tag>
              <el-tag v-else-if="row.status === 'interrupted'" type="warning" size="small">中断</el-tag>
              <span v-else class="panel-muted">完成</span>
            </template>
          </el-table-column>
          <el-table-column prop="summary" label="摘要" />
        </el-table>
        <el-empty v-if="!history.length && !loadingHistory" description="尚无轮次记录" />
      </el-tab-pane>
    </el-tabs>
  </section>
</template>

<style scoped>
.table {
  margin-top: 12px;
}
</style>
