<script setup lang="ts">
import { onMounted, ref } from "vue";
import {
  Clock,
  List,
  Monitor,
  Odometer,
  Refresh,
  Setting,
  Timer,
  VideoPlay,
} from "@element-plus/icons-vue";
import { useRouter } from "vue-router";

import { get } from "../api";
import EmptyState from "../components/EmptyState.vue";
import ErrorState from "../components/ErrorState.vue";
import MetricCard from "../components/MetricCard.vue";
import PageHeader from "../components/PageHeader.vue";
import StatusPill from "../components/StatusPill.vue";
import type { Overview, RunRecord } from "../types";
import { exitLabel, formatDuration, formatTime } from "../utils/format";

const router = useRouter();
const data = ref<Overview | null>(null);
const runs = ref<RunRecord[]>([]);
const loading = ref(true);
const error = ref("");

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [overview, history] = await Promise.all([
      get<Overview>("/api/overview"),
      get<{ runs: RunRecord[] }>("/api/runs?limit=5"),
    ]);
    data.value = overview;
    runs.value = history.runs;
  } catch (exception) {
    error.value = (exception as Error).message || "读取总览失败";
    data.value = null;
    runs.value = [];
  } finally {
    loading.value = false;
  }
}

function runTone(status?: string): "success" | "warning" | "danger" | "info" | "neutral" {
  if (status === "done") return "success";
  if (status === "running") return "info";
  if (status === "interrupted") return "warning";
  return "neutral";
}

function runLabel(record: RunRecord): string {
  if (record.status === "running") return "运行中";
  if (record.status === "interrupted") return "中断";
  if (record.status === "done") return "完成";
  return "—";
}

function healthLabel(value?: string | null): string {
  if (!value) return "";
  if (value === "healthy") return "健康";
  if (value === "unhealthy") return "异常";
  if (value === "starting") return "启动中";
  return value;
}

function summaryValue(value: unknown): string {
  if (Array.isArray(value)) return value.join(",");
  if (typeof value === "boolean") return value ? "开启" : "关闭";
  return String(value ?? "—");
}

onMounted(load);
</script>

<template>
  <section class="page">
    <PageHeader
      title="总览"
      subtitle="扫描器健康、上一轮结果与下一次执行"
      :icon="Odometer"
    >
      <el-button :loading="loading" @click="load">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
      <el-button type="primary" @click="router.push({ name: 'runs' })">
        <el-icon><VideoPlay /></el-icon>
        立即运行
      </el-button>
    </PageHeader>

    <ErrorState v-if="error" :message="error" @retry="load" />
    <el-skeleton v-else-if="loading && !data" :rows="6" animated />

    <template v-else-if="data">
      <div class="metrics">
        <MetricCard label="扫描容器" :icon="Monitor">
          <div class="row">
            <StatusPill
              :tone="data.scanner.state === 'running' ? 'success' : 'danger'"
              :label="data.scanner.state === 'running' ? '运行中' : '不可用'"
            />
            <span
              v-if="data.scanner.health && data.scanner.health !== 'healthy'"
              class="muted"
            >
              健康状态 {{ healthLabel(data.scanner.health) }}
            </span>
          </div>
          <p class="muted metric-note" v-if="data.scanner.reason">{{ data.scanner.reason }}</p>
          <p class="muted metric-note mono" v-else>{{ data.scanner.image ?? "—" }}</p>
        </MetricCard>

        <MetricCard label="上次结果" :icon="Clock">
          <div class="row">
            <StatusPill
              :tone="data.last_run?.scan_exit === 0 ? 'success' : data.last_run ? 'danger' : 'neutral'"
              :label="data.last_run ? `扫描 ${exitLabel(data.last_run.scan_exit)}` : '尚无记录'"
            />
            <span v-if="data.last_run" class="muted">
              发布 {{ exitLabel(data.last_run.publish_exit) }}
            </span>
          </div>
          <p class="muted metric-note" v-if="data.last_run">
            {{ formatTime(data.last_run.finished_at) }} · 耗时
            {{ formatDuration(data.last_run.duration_s) }}
          </p>
          <p class="muted metric-note" v-else>等待第一轮扫描</p>
        </MetricCard>

        <MetricCard label="下次执行" :icon="Timer">
          <span class="mono">{{ formatTime(data.next_runs[0]) }}</span>
          <p class="muted metric-note">
            {{ data.next_runs.length ? `共 ${data.next_runs.length} 次预览` : "调度表达式无效或未配置" }}
          </p>
        </MetricCard>

        <MetricCard label="轮次状态" :icon="VideoPlay">
          <StatusPill
            :tone="data.running ? 'info' : 'neutral'"
            :label="data.running ? '运行中' : '空闲'"
            :pulse="data.running"
          />
          <p class="muted metric-note">
            {{ data.running ? "扫描容器正在执行一轮任务" : "等待定时或手动触发" }}
          </p>
        </MetricCard>
      </div>

      <div class="grid overview-lower">
        <section class="panel">
          <header class="panel__head">
            <span class="panel-title"><el-icon><Timer /></el-icon>未来执行</span>
            <el-button text size="small" @click="router.push({ name: 'config', query: { tab: 'schedule' } })">
              <el-icon><Setting /></el-icon>
              调度设置
            </el-button>
          </header>
          <div class="panel__body">
            <ol v-if="data.next_runs.length" class="next-list">
              <li v-for="run in data.next_runs" :key="run" class="mono">{{ formatTime(run) }}</li>
            </ol>
            <EmptyState v-else title="暂无执行计划" description="检查 CRON_SCHEDULE 是否合法" />
          </div>
        </section>

        <section class="panel">
          <header class="panel__head">
            <span class="panel-title"><el-icon><Setting /></el-icon>生效配置</span>
            <el-button text size="small" @click="router.push({ name: 'config' })">
              <el-icon><Setting /></el-icon>
              参数设置
            </el-button>
          </header>
          <div class="panel__body">
            <dl class="kv">
              <template v-for="(value, key) in data.config_summary" :key="key">
                <dt>{{ key }}</dt>
                <dd class="mono">{{ summaryValue(value) }}</dd>
              </template>
            </dl>
          </div>
        </section>
      </div>

      <section class="panel overview-runs">
        <header class="panel__head">
          <span class="panel-title"><el-icon><List /></el-icon>最近轮次</span>
          <el-button text size="small" @click="router.push({ name: 'runs' })">
            <el-icon><List /></el-icon>
            全部轮次
          </el-button>
        </header>
        <div class="panel__body">
          <el-table v-if="runs.length" :data="runs" size="small">
            <el-table-column prop="run_id" label="轮次" min-width="180">
              <template #default="{ row }"><span class="mono">{{ row.run_id }}</span></template>
            </el-table-column>
            <el-table-column label="触发" width="80">
              <template #default="{ row }">{{ row.trigger ?? "—" }}</template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <StatusPill :tone="runTone(row.status)" :label="runLabel(row)" />
              </template>
            </el-table-column>
            <el-table-column label="扫描" width="110">
              <template #default="{ row }">{{ exitLabel(row.scan_exit) }}</template>
            </el-table-column>
            <el-table-column label="结束" min-width="170">
              <template #default="{ row }">{{ formatTime(row.finished_at) }}</template>
            </el-table-column>
          </el-table>
          <EmptyState v-else title="尚无轮次记录" description="下一轮扫描成功后显示在这里" />
        </div>
      </section>
    </template>
  </section>
</template>

<style scoped>
.panel-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.panel-title :deep(.el-icon) {
  color: var(--text-muted);
}

.metrics {
  display: grid;
  gap: var(--space-3);
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.metric-note {
  margin: 0;
  font-size: 12px;
  line-height: 18px;
  overflow-wrap: anywhere;
}

.overview-lower {
  margin-top: var(--space-3);
  grid-template-columns: minmax(280px, 1fr) minmax(320px, 1.4fr);
}

.next-list {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
}

.kv {
  display: grid;
  grid-template-columns: minmax(120px, auto) 1fr;
  gap: 8px 16px;
  margin: 0;
}

.kv dt {
  color: var(--text-muted);
  font-size: 12px;
}

.kv dd {
  margin: 0;
  overflow-wrap: anywhere;
}

.overview-runs {
  margin-top: var(--space-3);
}

@media (max-width: 1199px) {
  .panel-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.panel-title :deep(.el-icon) {
  color: var(--text-muted);
}

.metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 1023px) {
  .overview-lower {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 639px) {
  .panel-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.panel-title :deep(.el-icon) {
  color: var(--text-muted);
}

.metrics {
    grid-template-columns: 1fr;
  }
}
</style>
