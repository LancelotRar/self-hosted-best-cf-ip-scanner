<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import {
  CircleCheck,
  Refresh,
  Search,
  VideoPlay,
  Warning,
} from "@element-plus/icons-vue";

import { get, post } from "../api";
import EmptyState from "../components/EmptyState.vue";
import ErrorState from "../components/ErrorState.vue";
import LogConsole from "../components/LogConsole.vue";
import PageHeader from "../components/PageHeader.vue";
import StatusPill from "../components/StatusPill.vue";
import { useEventStream } from "../composables/useEventStream";
import { useTableWidths } from "../composables/useTableWidths";
import type { Overview, RunRecord } from "../types";
import {
  exitLabel,
  formatCount,
  formatDuration,
  formatTime,
  triggerLabel,
} from "../utils/format";
import {
  runLabel,
  runMatchesFilter,
  runQualified,
  runSummary,
  runTone,
  type RunFilter,
} from "../utils/run";

const router = useRouter();
const { widthFor: colWidth, onHeaderDragEnd: onColumnDragEnd } = useTableWidths("runs-history");

const activeTab = ref("run");
const ended = ref(false);
const runId = ref("");
const lines = ref<string[]>([]);
const error = ref("");
const history = ref<RunRecord[]>([]);
const overview = ref<Overview | null>(null);
const timezone = ref("UTC");
const loading = ref(false);
const triggering = ref(false);
const running = ref(false);
const page = ref(1);
const filter = ref<RunFilter>("all");
const query = ref("");
const pageSize = 20;

const scannerOnline = computed(() => overview.value?.scanner.state === "running");
const nextRun = computed(
  () =>
    overview.value?.schedule?.next_runs?.[0] ??
    overview.value?.next_runs?.[0] ??
    null,
);
const pushEnabled = computed(() => overview.value?.publish?.enabled ?? false);
const lastRun = computed(() => history.value[0] ?? null);

const filteredHistory = computed(() => {
  const needle = query.value.trim().toLowerCase();
  return history.value.filter((record) => {
    if (!runMatchesFilter(record, filter.value)) return false;
    if (!needle) return true;
    return `${record.run_id} ${record.summary ?? ""} ${triggerLabel(record.trigger)}`.toLowerCase().includes(needle);
  });
});

/** 历史轮次可能上百条，前端分页避免一次铺满整页。 */
const pagedHistory = computed(() => {
  const start = (page.value - 1) * pageSize;
  return filteredHistory.value.slice(start, start + pageSize);
});

const filterCounts = computed(() => ({
  all: history.value.length,
  done: history.value.filter((record) => runMatchesFilter(record, "done")).length,
  failed: history.value.filter((record) => runMatchesFilter(record, "failed")).length,
  interrupted: history.value.filter((record) => runMatchesFilter(record, "interrupted")).length,
  running: history.value.filter((record) => runMatchesFilter(record, "running")).length,
}));

const filterOptions: Array<{ value: RunFilter; label: string }> = [
  { value: "all", label: "全部" },
  { value: "done", label: "完成" },
  { value: "failed", label: "失败" },
  { value: "interrupted", label: "中断" },
  { value: "running", label: "运行中" },
];

const { status, lastReceived, connect } = useEventStream(
  () => (runId.value ? `/api/runs/${encodeURIComponent(runId.value)}/stream` : "/api/runs/pending/stream"),
  {
    onMessage: (data) => lines.value.push(data),
    onDone: (code) => {
      ended.value = true;
      lines.value.push(`[结束] 退出码 ${code}`);
      ElMessage.info(`本轮结束，退出码 ${code}`);
      void load();
    },
    onError: (message) => lines.value.push(`[${message}]`),
    retryOnError: false,
  },
);

async function load(silent = false) {
  if (!silent) loading.value = true;
  error.value = "";
  try {
    const [data, ov] = await Promise.all([
      get<{ runs: RunRecord[]; timezone: string }>("/api/runs?limit=200"),
      get<Overview>("/api/overview"),
    ]);
    history.value = data.runs;
    overview.value = ov;
    timezone.value = data.timezone || ov.timezone || "UTC";
    running.value = ov.running || data.runs.some((record) => record.status === "running");
    if ((page.value - 1) * pageSize >= filteredHistory.value.length) page.value = 1;
  } catch (exception) {
    if (!silent) error.value = (exception as Error).message || "读取运行记录失败";
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
    await load(true);
  } catch (exception) {
    error.value = (exception as Error).message;
    ElMessage.error((exception as Error).message);
  } finally {
    triggering.value = false;
  }
}

function resetFilters() {
  filter.value = "all";
  query.value = "";
}

watch([filter, query], () => {
  page.value = 1;
});

let poll: number | undefined;

onMounted(async () => {
  await load();
  const live = history.value.find(
    (record) => record.status === "running" && record.trigger === "panel",
  );
  if (live) {
    runId.value = live.run_id;
    lines.value = [`[已接上进行中的轮次 ${live.run_id}]`];
    connect();
  }
  poll = window.setInterval(() => {
    if (running.value && document.visibilityState === "visible") void load(true);
  }, 15_000);
});

onBeforeUnmount(() => {
  if (poll) window.clearInterval(poll);
});
</script>

<template>
  <section class="page">
    <PageHeader
      title="手动运行"
      subtitle="手动执行与计划任务共用同一套配置，仅触发方式不同"
    >
      <template #actions>
        <el-button :loading="loading" @click="load()">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
        <el-button type="primary" :loading="triggering" :disabled="running" @click="trigger">
          <el-icon><VideoPlay /></el-icon>
          立即执行一轮
        </el-button>
      </template>
    </PageHeader>

    <ErrorState v-if="error" :message="error" @retry="load()" />

    <!-- 运行前检查：把“为什么不能跑 / 下一次什么时候跑”放在按钮下方 -->
    <section class="preflight" aria-label="运行前检查">
      <div class="preflight__item">
        <StatusPill
          :tone="scannerOnline ? 'success' : 'danger'"
          :label="scannerOnline ? '扫描器在线' : '扫描器离线'"
        />
        <span class="preflight__text">{{ scannerOnline ? "可以执行手动扫描" : overview?.scanner.reason || "面板无法连接扫描容器" }}</span>
      </div>
      <div class="preflight__item">
        <span class="preflight__label">下一次计划</span>
        <span class="mono">{{ formatTime(nextRun, timezone) }}</span>
      </div>
      <div class="preflight__item">
        <span class="preflight__label">发布</span>
        <span>{{ pushEnabled ? "扫描成功后自动推送" : "未开启，仅本地产物" }}</span>
      </div>
      <div v-if="running" class="preflight__item preflight__item--live">
        <StatusPill tone="info" label="已有轮次在运行" pulse />
        <span class="preflight__text">同一时间只允许一轮，完成后再触发。</span>
      </div>
    </section>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="实时输出" name="run">
        <LogConsole
          v-if="runId"
          :lines="lines"
          :status="status"
          :last-received="lastReceived"
          :ended="ended"
          :time-zone="timezone"
        />

        <section v-else class="run-intro panel">
          <div class="run-intro__copy">
            <h2>手动执行一轮</h2>
            <p>
              触发后会在扫描容器内执行同一套流程：TCP 握手初筛 → 边缘端点校验 → 生成产物；
              开启发布时再推送到 Git 仓库。
            </p>
            <ol class="run-intro__steps">
              <li><span>1</span>确认扫描器在线，参数已保存</li>
              <li><span>2</span>点击「立即执行一轮」，输出会实时显示</li>
              <li><span>3</span>结束后在总览或历史轮次查看产物与合格数</li>
            </ol>
          </div>
          <div class="run-intro__side">
            <div class="run-intro__fact">
              <span class="muted">最近一轮</span>
              <strong v-if="lastRun">{{ runLabel(lastRun) }}</strong>
              <strong v-else>—</strong>
              <small v-if="lastRun" class="muted">
                {{ runSummary(lastRun) }} · {{ formatDuration(lastRun.duration_s) }}
              </small>
              <small v-else class="muted">还没有运行记录</small>
            </div>
            <div v-if="running" class="run-intro__notice">
              <el-icon><Warning /></el-icon>
              <span>计划任务正在执行。请到「查看日志」页查看实时输出。</span>
              <el-button size="small" @click="router.push({ name: 'logs' })">去日志页</el-button>
            </div>
            <el-button type="primary" :loading="triggering" :disabled="running" @click="trigger">
              <el-icon><VideoPlay /></el-icon>
              立即执行一轮
            </el-button>
          </div>
        </section>

        <section v-if="ended" class="run-result panel" aria-live="polite">
          <el-icon class="run-result__icon"><CircleCheck /></el-icon>
          <div>
            <strong>本轮已结束</strong>
            <p class="muted">退出码与产物在「历史轮次」和总览中查看。</p>
          </div>
          <el-button size="small" @click="activeTab = 'history'">查看历史</el-button>
        </section>
      </el-tab-pane>

      <el-tab-pane label="历史轮次" name="history">
        <div class="history-toolbar">
          <div class="filter-chips" role="group" aria-label="按状态筛选">
            <button
              v-for="option in filterOptions"
              :key="option.value"
              type="button"
              class="filter-chip"
              :class="{ 'filter-chip--active': filter === option.value }"
              @click="filter = option.value"
            >
              {{ option.label }}
              <span class="filter-chip__count">{{ filterCounts[option.value] }}</span>
            </button>
          </div>
          <el-input
            v-model="query"
            clearable
            placeholder="搜索轮次或摘要"
            class="history-search"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <span class="spacer" />
          <span class="muted">共 {{ filteredHistory.length }} 轮</span>
        </div>

        <section v-if="history.length" class="panel">
          <div class="panel__body">
            <el-table
              v-if="pagedHistory.length"
              border
              :data="pagedHistory"
              size="small"
              class="history-table"
              @header-dragend="onColumnDragEnd"
            >
              <el-table-column label="轮次" :width="colWidth('轮次')" min-width="170">
                <template #default="{ row }"><span class="mono">{{ row.run_id }}</span></template>
              </el-table-column>
              <el-table-column label="触发" :width="colWidth('触发') ?? 86" align="center">
                <template #default="{ row }"><span class="nowrap">{{ triggerLabel(row.trigger) }}</span></template>
              </el-table-column>
              <el-table-column label="状态" :width="colWidth('状态')" min-width="116" align="center">
                <template #default="{ row }">
                  <StatusPill :tone="runTone(row)" :label="runLabel(row)" />
                </template>
              </el-table-column>
              <el-table-column label="合格" :width="colWidth('合格') ?? 84" align="right">
                <template #default="{ row }">
                  <span class="num">{{ formatCount(runQualified(row)) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="扫描" :width="colWidth('扫描') ?? 96" align="center">
                <template #default="{ row }"><span class="nowrap">{{ exitLabel(row.scan_exit) }}</span></template>
              </el-table-column>
              <el-table-column label="发布" :width="colWidth('发布') ?? 96" align="center">
                <template #default="{ row }"><span class="nowrap">{{ exitLabel(row.publish_exit) }}</span></template>
              </el-table-column>
              <el-table-column label="耗时" :width="colWidth('耗时') ?? 78" align="right">
                <template #default="{ row }"><span class="num">{{ formatDuration(row.duration_s) }}</span></template>
              </el-table-column>
              <el-table-column label="开始" :width="colWidth('开始')" min-width="160">
                <template #default="{ row }"><span class="mono nowrap">{{ formatTime(row.started_at, timezone) }}</span></template>
              </el-table-column>
              <el-table-column label="摘要" :width="colWidth('摘要')" min-width="150" show-overflow-tooltip>
                <template #default="{ row }">
                  <span class="muted">{{ runSummary(row) }}</span>
                </template>
              </el-table-column>
            </el-table>
            <EmptyState
              v-else
              compact
              title="没有匹配的轮次"
              description="换个状态或清空搜索词再试"
              action-label="重置筛选"
              @action="resetFilters"
            />
            <el-pagination
              v-if="filteredHistory.length > pageSize"
              layout="prev, pager, next"
              :total="filteredHistory.length"
              :page-size="pageSize"
              :current-page="page"
              @current-change="page = $event"
            />
          </div>
        </section>
        <EmptyState
          v-else
          compact
          title="尚无轮次记录"
          description="计划任务或手动执行完成后出现在这里"
          action-label="刷新"
          @action="load()"
        />
      </el-tab-pane>
    </el-tabs>
  </section>
</template>

<style scoped>
.preflight {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  flex-wrap: wrap;
  padding: 10px 14px;
  margin-bottom: var(--space-4);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
  font-size: var(--fs-meta);
}

.preflight__item {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.preflight__label {
  color: var(--text-faint);
}

.preflight__text {
  color: var(--text-muted);
  overflow-wrap: anywhere;
}

.preflight__item--live {
  margin-left: auto;
}

.run-intro {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(220px, 1fr);
  gap: var(--space-5);
  max-width: 900px;
  margin-inline: auto;
  padding: 26px;
}

.run-intro__copy h2 {
  margin: 0;
  font-size: var(--fs-h2);
  line-height: 26px;
  letter-spacing: -0.01em;
}

.run-intro__copy > p {
  margin: 8px 0 0;
  max-width: 62ch;
  color: var(--text-muted);
  font-size: var(--fs-body);
  line-height: 21px;
}

.run-intro__steps {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: var(--space-5) 0 0;
  padding: 0;
  list-style: none;
  color: var(--text-muted);
  font-size: var(--fs-body);
}

.run-intro__steps li {
  display: flex;
  align-items: center;
  gap: 10px;
}

.run-intro__steps span {
  display: inline-grid;
  place-items: center;
  flex: 0 0 auto;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--surface-2);
  color: var(--text);
  font-size: var(--fs-micro);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.run-intro__side {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  align-items: flex-start;
  padding-left: var(--space-5);
  border-left: 1px solid var(--border-soft);
}

.run-intro__fact {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.run-intro__fact strong {
  font-size: var(--fs-h2);
  line-height: 26px;
}

.run-intro__fact small {
  font-size: var(--fs-meta);
}

.run-intro__notice {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  flex-wrap: wrap;
  padding: 10px;
  border-radius: var(--radius-sm);
  background: var(--tone-warning-soft);
  color: var(--text);
  font-size: var(--fs-meta);
  line-height: 18px;
}

.run-result {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  max-width: 900px;
  margin-inline: auto;
  margin-top: var(--space-4);
  padding: 14px 18px;
}

.run-result__icon {
  color: var(--success);
  font-size: 20px;
}

.run-result p {
  margin: 1px 0 0;
  font-size: var(--fs-meta);
}

.run-result .el-button {
  margin-left: auto;
}

.history-toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-bottom: var(--space-4);
}

.filter-chips {
  display: flex;
  gap: 2px;
  flex-wrap: wrap;
}

.filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 10px;
  border: 1px solid transparent;
  border-radius: 999px;
  background: none;
  color: var(--text-muted);
  font-family: inherit;
  font-size: var(--fs-meta);
  cursor: pointer;
  transition: background-color var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease);
}

.filter-chip:hover {
  background: var(--surface-2);
  color: var(--text);
}

.filter-chip--active {
  background: var(--primary-soft);
  color: var(--text);
  border-color: var(--border);
  font-weight: 600;
}

.filter-chip__count {
  color: var(--text-faint);
  font-variant-numeric: tabular-nums;
}

.history-search {
  max-width: 260px;
}

.nowrap {
  white-space: nowrap;
}

@media (max-width: 900px) {
  .run-intro {
    grid-template-columns: minmax(0, 1fr);
    padding: var(--space-5);
  }

  .run-intro__side {
    padding-left: 0;
    padding-top: var(--space-4);
    border-left: 0;
    border-top: 1px solid var(--border-soft);
    align-items: stretch;
  }

  .history-search {
    max-width: none;
    flex: 1 1 100%;
  }
}
</style>
