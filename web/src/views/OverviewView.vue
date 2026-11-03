<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import {
  DataLine,
  Document,
  FolderOpened,
  Monitor,
  Odometer,
  Timer,
  Upload,
  VideoPlay,
} from "@element-plus/icons-vue";

import { get } from "../api";
import EmptyState from "../components/EmptyState.vue";
import ErrorState from "../components/ErrorState.vue";
import PageHeader from "../components/PageHeader.vue";
import StatusPill from "../components/StatusPill.vue";
import type { LibraryDocument, OutputFile, Overview, Param, RunRecord } from "../types";
import { exitLabel, formatDuration, formatSize, formatTime } from "../utils/format";

interface PublishResponse {
  hash: string;
  params: Param[];
  last: RunRecord | null;
}

interface Preview {
  name: string;
  kind: "text" | "csv" | "binary";
  size: number;
  mtime: string;
  sha256: string;
  content?: string;
  headers?: string[];
  rows?: string[][];
  truncated?: boolean;
}

const loading = ref(true);
const error = ref("");

const overview = ref<Overview | null>(null);
const runs = ref<RunRecord[]>([]);
const files = ref<OutputFile[]>([]);
const library = ref<LibraryDocument | null>(null);
const publish = ref<PublishResponse | null>(null);
const cronExpression = ref("");
const timezone = ref("");

const previewVisible = ref(false);
const previewLoading = ref(false);
const currentPreview = ref<Preview | null>(null);

function paramValue(name: string): unknown {
  return publish.value?.params.find((param) => param.name === name)?.value;
}

const pushEnabled = () => paramValue("GIT_PUSH_ENABLED") === true;

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [ov, history, outputs, lib, pub, config] = await Promise.all([
      get<Overview>("/api/overview"),
      get<{ runs: RunRecord[] }>("/api/runs?limit=20"),
      get<{ read_at: string; files: OutputFile[] }>("/api/outputs"),
      get<LibraryDocument>("/api/library"),
      get<PublishResponse>("/api/publish"),
      get<{ params: Param[] }>("/api/config"),
    ]);
    overview.value = ov;
    runs.value = history.runs;
    files.value = outputs.files;
    library.value = lib;
    publish.value = pub;
    const cron = config.params.find((param) => param.name === "CRON_SCHEDULE");
    const tz = config.params.find((param) => param.name === "TZ");
    cronExpression.value = cron ? String(cron.value) : "";
    timezone.value = tz ? String(tz.value) : "";
  } catch (exception) {
    error.value = (exception as Error).message || "读取总览失败";
  } finally {
    loading.value = false;
  }
}

/** 把常见 cron 表达成可读间隔；不认识的表达式原样说明。 */
function describeCron(expr: string): string {
  const parts = expr.trim().split(/\s+/);
  if (parts.length === 5) {
    const [minute, hour] = parts;
    const minuteStep = /^\*\/(\d+)$/.exec(minute);
    const hourStep = /^\*\/(\d+)$/.exec(hour);
    if (minuteStep) return `每 ${minuteStep[1]} 分钟`;
    if (hourStep) {
      return minute === "0"
        ? `每 ${hourStep[1]} 小时`
        : `每 ${hourStep[1]} 小时（第 ${minute} 分）`;
    }
    if (/^\d+$/.test(minute) && /^\d+$/.test(hour) && parts.slice(2).every((p) => p === "*")) {
      return `每天 ${hour.padStart(2, "0")}:${minute.padStart(2, "0")}`;
    }
  }
  return parts.length === 5 ? "自定义表达式" : "自定义表达式（含秒/年）";
}

function healthLabel(value?: string | null): string {
  if (!value) return "";
  if (value === "healthy") return "健康";
  if (value === "unhealthy") return "异常";
  if (value === "starting") return "启动中";
  return value;
}

function runLabel(record: RunRecord): string {
  if (record.status === "running") return "运行中";
  if (record.status === "interrupted") return "中断";
  if (record.status === "done") return "完成";
  return "—";
}

function runTone(record: RunRecord): "success" | "warning" | "info" | "neutral" {
  if (record.status === "running") return "info";
  if (record.status === "interrupted") return "warning";
  if (record.status === "done") return "success";
  return "neutral";
}

async function openPreview(file: OutputFile) {
  previewVisible.value = true;
  previewLoading.value = true;
  currentPreview.value = null;
  try {
    currentPreview.value = await get<Preview>(`/api/outputs/${encodeURIComponent(file.name)}`);
  } catch (exception) {
    ElMessage.error((exception as Error).message);
    previewVisible.value = false;
  } finally {
    previewLoading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section class="page">
    <PageHeader
      title="总览"
      subtitle="扫描器、IP 库、计划、运行、产物与推送情况的综合视图"
      :icon="Odometer"
    />

    <ErrorState v-if="error" :message="error" @retry="load" />
    <el-skeleton v-else-if="loading" :rows="8" animated />

    <div v-else-if="overview" class="overview">
      <!-- 1. 容器状态 -->
      <section class="panel">
        <header class="panel__head">
          <span class="section-title"><el-icon><Monitor /></el-icon>容器状态</span>
        </header>
        <div class="panel__body">
          <div class="status-line">
            <span
              class="status-dot"
              :class="overview.scanner.state === 'running' ? 'status-dot--on' : 'status-dot--off'"
              aria-hidden="true"
            />
            <strong>{{ overview.scanner.state === "running" ? "扫描容器在线" : "扫描容器离线" }}</strong>
            <StatusPill
              :tone="overview.running ? 'info' : 'neutral'"
              :label="overview.running ? '运行中' : '空闲'"
              :pulse="overview.running"
            />
          </div>
          <dl class="kv">
            <dt>健康状态</dt>
            <dd>{{ healthLabel(overview.scanner.health) || "—" }}</dd>
            <dt>镜像</dt>
            <dd class="mono">{{ overview.scanner.image ?? "—" }}</dd>
            <dt>启动时间</dt>
            <dd class="mono">{{ formatTime(overview.scanner.started_at) }}</dd>
            <dt v-if="overview.scanner.reason">离线原因</dt>
            <dd v-if="overview.scanner.reason">{{ overview.scanner.reason }}</dd>
          </dl>
        </div>
      </section>

      <!-- 2. IP 库信息 -->
      <section class="panel">
        <header class="panel__head">
          <span class="section-title"><el-icon><DataLine /></el-icon>IP 库信息</span>
        </header>
        <div class="panel__body">
          <template v-if="library">
            <p class="section-note">
              {{ library.line_count }} 行 · 网段 {{ library.stats.networks }} · 固定条目
              {{ library.stats.fixed }} · 跳过 {{ library.stats.skipped }} · 修改时间
              {{ formatTime(library.mtime) }}
            </p>
            <pre class="library-preview mono">{{ library.content }}</pre>
          </template>
          <EmptyState v-else title="尚未读取到 IP 库" description="请检查 ./data/ip-library.txt" />
        </div>
      </section>

      <!-- 3. 计划详情 -->
      <section class="panel">
        <header class="panel__head">
          <span class="section-title"><el-icon><Timer /></el-icon>计划详情</span>
        </header>
        <div class="panel__body">
          <dl class="kv kv--four">
            <dt>调度表达式</dt>
            <dd class="mono">{{ cronExpression || "—" }}</dd>
            <dt>执行间隔</dt>
            <dd>{{ describeCron(cronExpression) }}</dd>
            <dt>下次执行</dt>
            <dd class="mono">{{ formatTime(overview.next_runs[0]) }}</dd>
            <dt>时区</dt>
            <dd>{{ timezone || "—" }}</dd>
          </dl>
        </div>
      </section>

      <!-- 4. 近期扫描情况 -->
      <section class="panel">
        <header class="panel__head">
          <span class="section-title"><el-icon><VideoPlay /></el-icon>近期扫描情况</span>
        </header>
        <div class="panel__body">
          <el-table v-if="runs.length" :data="runs" size="small" height="300" class="scroll-table">
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
            <el-table-column label="耗时" width="90">
              <template #default="{ row }">{{ formatDuration(row.duration_s) }}</template>
            </el-table-column>
            <el-table-column label="结束" min-width="170">
              <template #default="{ row }">{{ formatTime(row.finished_at) }}</template>
            </el-table-column>
          </el-table>
          <EmptyState v-else title="尚无扫描记录" description="定时任务或手动执行完成后显示在这里" />
        </div>
      </section>

      <!-- 5. 产物情况 -->
      <section class="panel">
        <header class="panel__head">
          <span class="section-title"><el-icon><FolderOpened /></el-icon>产物情况</span>
        </header>
        <div class="panel__body">
          <el-table v-if="files.length" :data="files" size="small" height="280" class="scroll-table">
            <el-table-column label="文件" min-width="200">
              <template #default="{ row }"><span class="mono">{{ row.name }}</span></template>
            </el-table-column>
            <el-table-column label="大小" width="110">
              <template #default="{ row }">{{ formatSize(row.size) }}</template>
            </el-table-column>
            <el-table-column label="修改时间" width="180">
              <template #default="{ row }">{{ formatTime(row.mtime) }}</template>
            </el-table-column>
            <el-table-column label="预览" width="100">
              <template #default="{ row }">
                <el-button size="small" @click="openPreview(row)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>
          <EmptyState v-else title="尚无产物" description="下一轮扫描成功后生成订阅列表与明细表" />
        </div>
      </section>

      <!-- 6. 推送情况 -->
      <section class="panel">
        <header class="panel__head">
          <span class="section-title"><el-icon><Upload /></el-icon>推送情况</span>
        </header>
        <div class="panel__body">
          <div class="status-line">
            <StatusPill
              :tone="pushEnabled() ? 'success' : 'neutral'"
              :label="pushEnabled() ? '推送已开启' : '推送已关闭'"
            />
          </div>
          <dl class="kv">
            <dt>目标仓库</dt>
            <dd class="mono">{{ paramValue("GIT_REPO_URL") || "—" }}</dd>
            <dt>分支 / 目录</dt>
            <dd class="mono">
              {{ paramValue("GIT_BRANCH") || "—" }} /
              {{ paramValue("GIT_OUTPUT_SUBDIR") || "—" }}
            </dd>
            <template v-if="!pushEnabled()">
              <dt>推送</dt>
              <dd class="muted">已关闭，不执行推送</dd>
            </template>
            <template v-else-if="publish?.last">
              <dt>上次推送</dt>
              <dd class="mono">{{ formatTime(publish.last.finished_at) }}</dd>
              <dt>扫描 / 推送</dt>
              <dd>
                {{ exitLabel(publish.last.scan_exit) }} /
                {{ exitLabel(publish.last.publish_exit) }}
              </dd>
            </template>
            <template v-else>
              <dt>上次推送</dt>
              <dd class="muted">尚无推送记录</dd>
            </template>
          </dl>
        </div>
      </section>
    </div>

    <el-dialog
      v-model="previewVisible"
      :title="currentPreview?.name ?? '产物预览'"
      width="min(900px, 92vw)"
      destroy-on-close
    >
      <el-skeleton v-if="previewLoading" :rows="6" animated />
      <template v-else-if="currentPreview">
        <p class="section-note">
          {{ formatSize(currentPreview.size) }} · {{ formatTime(currentPreview.mtime) }} · sha256
          <span class="mono">{{ currentPreview.sha256.slice(0, 12) }}…</span>
        </p>
        <el-table
          v-if="currentPreview.kind === 'csv'"
          :data="currentPreview.rows ?? []"
          size="small"
          height="420"
        >
          <el-table-column
            v-for="(header, index) in currentPreview.headers"
            :key="index"
            :label="header"
            min-width="120"
          >
            <template #default="{ row }">{{ row[index] }}</template>
          </el-table-column>
        </el-table>
        <pre v-else-if="currentPreview.kind === 'text'" class="dialog-preview mono">{{
          currentPreview.content
        }}</pre>
        <EmptyState v-else title="该类型不支持预览" description="请在宿主机下载后查看" />
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.overview {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.section-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.section-title :deep(.el-icon) {
  color: var(--text-muted);
}

.section-note {
  margin: 0 0 var(--space-3);
  color: var(--text-muted);
  font-size: 12px;
  line-height: 18px;
}

.status-line {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex: 0 0 auto;
}

.status-dot--on {
  background: var(--success);
  animation: pulse-ok 2.2s ease-out infinite;
}

.status-dot--off {
  background: var(--danger);
  animation: pulse-bad 1.6s ease-out infinite;
}

.kv {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 8px 16px;
  margin: 0;
}

.kv--four {
  grid-template-columns: 110px minmax(120px, 1fr) 110px 1fr;
}

.kv dt {
  color: var(--text-muted);
  font-size: 12px;
}

.kv dd {
  margin: 0;
  overflow-wrap: anywhere;
}

.library-preview {
  margin: 0;
  max-height: 320px;
  overflow: auto;
  padding: var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  color: var(--text);
  font-size: 12px;
  line-height: 18px;
  white-space: pre;
  tab-size: 4;
}

.dialog-preview {
  max-height: 440px;
  overflow: auto;
  margin: 0;
  padding: var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  font-size: 12px;
  line-height: 18px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

@keyframes pulse-ok {
  0% {
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--success) 55%, transparent);
  }
  70% {
    box-shadow: 0 0 0 7px transparent;
  }
  100% {
    box-shadow: 0 0 0 0 transparent;
  }
}

@keyframes pulse-bad {
  0% {
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--danger) 55%, transparent);
  }
  70% {
    box-shadow: 0 0 0 7px transparent;
  }
  100% {
    box-shadow: 0 0 0 0 transparent;
  }
}

@media (max-width: 767px) {
  .kv,
  .kv--four {
    grid-template-columns: 110px 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  .status-dot {
    animation: none !important;
  }
}
</style>
