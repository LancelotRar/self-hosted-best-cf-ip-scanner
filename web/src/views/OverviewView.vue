<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import {
  DataLine,
  FolderOpened,
  Monitor,
  Timer,
  Upload,
  VideoPlay,
} from "@element-plus/icons-vue";

import { get } from "../api";
import EmptyState from "../components/EmptyState.vue";
import { useTableWidths } from "../composables/useTableWidths";
import ErrorState from "../components/ErrorState.vue";
import PageHeader from "../components/PageHeader.vue";
import StatusPill from "../components/StatusPill.vue";
import type { LibraryDocument, OutputFile, Overview, Param, RunRecord } from "../types";
import { exitLabel, formatDuration, formatMinute, formatSize, formatTime } from "../utils/format";

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
const { widthFor: runsWidth, onHeaderDragEnd: onRunsDragEnd } = useTableWidths("overview-runs");
const { widthFor: filesWidth, onHeaderDragEnd: onFilesDragEnd } = useTableWidths("overview-outputs");
const { widthFor: previewWidth, onHeaderDragEnd: onPreviewDragEnd } = useTableWidths("preview-csv");
const publish = ref<PublishResponse | null>(null);
const cronExpression = ref("");
const timezone = ref("");

const previewVisible = ref(false);
const previewLoading = ref(false);
const currentPreview = ref<Preview | null>(null);

const scannerOnline = computed(() => overview.value?.scanner.state === "running");

/** 容器已运行时长：分钟级即可，超过一天用 d/h。 */
function uptimeText(started?: string | null): string {
  if (!started) return "—";
  const start = new Date(started).getTime();
  if (Number.isNaN(start)) return "—";
  const minutes = Math.max(0, Math.floor((Date.now() - start) / 60_000));
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours < 24) return rest ? `${hours}h ${rest}m` : `${hours}h`;
  return `${Math.floor(hours / 24)}d ${hours % 24}h`;
}

const uptime = computed(() => uptimeText(overview.value?.scanner.started_at));

/** 镜像名太长，卡片主值只放 tag，完整名字放到注释里。 */
const imageTag = computed(() => {
  const image = overview.value?.scanner.image ?? "";
  if (!image) return "—";
  const tag = image.split(":").pop();
  return tag && tag !== image ? tag : image;
});

/** 注释说明已移到「参数调整 · 自定义 IP 库」，总览只列地址条目。 */
const libraryEntries = computed(() =>
  (library.value?.content ?? "")
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#")),
);

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

const WEEKDAYS = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];

/** 把常见 cron 表达成可读间隔；不认识的表达式原样说明。 */
function describeCron(expr: string): string {
  const parts = expr.trim().split(/\s+/);
  if (parts.length !== 5) return "按自定义计划执行";

  const [minute, hour, day, month, weekday] = parts;
  const clock = `${hour.padStart(2, "0")}:${minute.padStart(2, "0")}`;
  const numeric = (value: string) => /^\d+$/.test(value);

  const minuteStep = /^\*\/(\d+)$/.exec(minute);
  if (minuteStep) return `每 ${minuteStep[1]} 分钟`;

  const hourStep = /^\*\/(\d+)$/.exec(hour);
  if (hourStep) {
    return minute === "0"
      ? `每 ${hourStep[1]} 小时`
      : `每 ${hourStep[1]} 小时（第 ${minute} 分）`;
  }

  if (!numeric(minute) || !numeric(hour)) return "按自定义计划执行";

  if (day === "*" && month === "*" && weekday === "*") return `每天 ${clock}`;
  if (day === "*" && month === "*" && numeric(weekday)) {
    const index = Number(weekday) % 7;
    return `每${WEEKDAYS[index]} ${clock}`;
  }
  if (numeric(day) && month === "*" && weekday === "*") {
    return `每月 ${Number(day)} 日 ${clock}`;
  }
  if (numeric(day) && numeric(month) && weekday === "*") {
    return `每年 ${Number(month)} 月 ${Number(day)} 日 ${clock}`;
  }
  return "按自定义计划执行";
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

/** 开始时间按分钟展示；缺失记录时从 run_id（`YYYYMMDDTHHMMSS-序号`）回退解析。 */
function startText(record: RunRecord): string {
  if (record.started_at) return formatMinute(record.started_at);
  const match = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})/.exec(record.run_id);
  if (!match) return record.run_id;
  const [, year, month, day, hour, minute] = match;
  return `${year}-${month}-${day} ${hour}:${minute}`;
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
      title="信息总览"
      subtitle="扫描器、IP 库、计划、运行、产物与推送情况的综合视图"
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
          <div class="stat-row">
            <article class="stat">
              <span class="stat__label">扫描容器</span>
              <strong class="stat__value" :class="scannerOnline ? 'is-on' : 'is-off'">
                {{ scannerOnline ? "在线" : "离线" }}
              </strong>
              <span class="stat__note">健康状态 · {{ healthLabel(overview.scanner.health) || "—" }}</span>
            </article>

            <article class="stat">
              <span class="stat__label">当前任务</span>
              <strong class="stat__value" :class="overview.running ? 'is-busy' : ''">
                {{ overview.running ? "运行中" : "空闲" }}
              </strong>
              <span class="stat__note">
                上次完成 · {{ formatTime(overview.last_run?.finished_at) }}
              </span>
            </article>

            <article class="stat">
              <span class="stat__label">镜像</span>
              <strong class="stat__value">{{ imageTag }}</strong>
              <span class="stat__note" :title="overview.scanner.image ?? ''">
                {{ overview.scanner.image ?? "—" }}
              </span>
            </article>

            <article class="stat">
              <span class="stat__label">已运行</span>
              <strong class="stat__value">{{ uptime }}</strong>
              <span class="stat__note">启动于 {{ formatTime(overview.scanner.started_at, false) }}</span>
            </article>
          </div>

          <p v-if="overview.scanner.reason" class="stat-alert">
            离线原因：{{ overview.scanner.reason }}
          </p>
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
            <p class="section-note muted">
              只列出地址条目；格式说明与编辑在「参数调整 · 自定义 IP 库」。
            </p>
            <div class="library-preview mono">
              <span v-for="(entry, index) in libraryEntries" :key="index">{{ entry }}</span>
            </div>
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
          <div class="facts">
            <div class="fact">
              <span class="fact__label">计划任务</span>
              <span class="fact__value">{{ describeCron(cronExpression) }}</span>
            </div>
            <div class="fact">
              <span class="fact__label">下一次运行时间</span>
              <span class="fact__value mono">{{ formatTime(overview.next_runs[0]) }}</span>
            </div>
            <div class="fact">
              <span class="fact__label">时区</span>
              <span class="fact__value">{{ timezone || "—" }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 4. 近期扫描情况 -->
      <section class="panel">
        <header class="panel__head">
          <span class="section-title"><el-icon><VideoPlay /></el-icon>近期扫描情况</span>
        </header>
        <div class="panel__body">
          <el-table
            border
            v-if="runs.length"
            :data="runs"
            size="small"
            max-height="300"
            class="scroll-table"
            @header-dragend="onRunsDragEnd"
          >
            <el-table-column label="开始时间" :width="runsWidth('开始时间')" min-width="230">
              <template #default="{ row }">
                <span class="mono">{{ startText(row) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="触发" :width="runsWidth('触发')" min-width="77">
              <template #default="{ row }">{{ row.trigger ?? "—" }}</template>
            </el-table-column>
            <el-table-column label="状态" :width="runsWidth('状态')" min-width="102">
              <template #default="{ row }">
                <StatusPill :tone="runTone(row)" :label="runLabel(row)" />
              </template>
            </el-table-column>
            <el-table-column label="扫描" :width="runsWidth('扫描')" min-width="115">
              <template #default="{ row }">{{ exitLabel(row.scan_exit) }}</template>
            </el-table-column>
            <el-table-column label="耗时" :width="runsWidth('耗时')" min-width="115">
              <template #default="{ row }">{{ formatDuration(row.duration_s) }}</template>
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
          <el-table
            border
            v-if="files.length"
            :data="files"
            size="small"
            max-height="280"
            class="scroll-table"
            @header-dragend="onFilesDragEnd"
          >
            <el-table-column label="文件" :width="filesWidth('文件')" min-width="175" show-overflow-tooltip>
              <template #default="{ row }"><span class="mono">{{ row.name }}</span></template>
            </el-table-column>
            <el-table-column label="大小" :width="filesWidth('大小')" min-width="175">
              <template #default="{ row }">{{ formatSize(row.size) }}</template>
            </el-table-column>
            <el-table-column label="修改时间" :width="filesWidth('修改时间')" min-width="175">
              <template #default="{ row }">{{ formatTime(row.mtime) }}</template>
            </el-table-column>
            <el-table-column label="预览" :width="filesWidth('预览')" min-width="175" >
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
          <div class="facts">
            <div class="fact">
              <span class="fact__label">目标仓库</span>
              <span class="fact__value mono">{{ paramValue("GIT_REPO_URL") || "—" }}</span>
            </div>
            <div class="fact">
              <span class="fact__label">分支 / 目录</span>
              <span class="fact__value mono">
                {{ paramValue("GIT_BRANCH") || "—" }} /
                {{ paramValue("GIT_OUTPUT_SUBDIR") || "—" }}
              </span>
            </div>
            <div class="fact">
              <span class="fact__label">推送</span>
              <span class="fact__value" :class="{ muted: !pushEnabled() }">
                {{ pushEnabled() ? "已开启" : "已关闭，不执行推送" }}
              </span>
            </div>
            <div v-if="pushEnabled()" class="fact">
              <span class="fact__label">上次推送</span>
              <span class="fact__value mono">
                {{ publish?.last ? formatTime(publish.last.finished_at) : "尚无推送记录" }}
              </span>
            </div>
            <div v-if="pushEnabled() && publish?.last" class="fact">
              <span class="fact__label">扫描 / 推送</span>
              <span class="fact__value">
                {{ exitLabel(publish.last.scan_exit) }} /
                {{ exitLabel(publish.last.publish_exit) }}
              </span>
            </div>
          </div>
        </div>
      </section>
    </div>

    <el-dialog
      v-model="previewVisible"
      :title="currentPreview?.name ?? '产物预览'"
      width="min(640px, 92vw)"
      align-center
      destroy-on-close
    >
      <el-skeleton v-if="previewLoading" :rows="6" animated />
      <template v-else-if="currentPreview">
        <p class="section-note">
          {{ formatSize(currentPreview.size) }} · {{ formatTime(currentPreview.mtime) }}
        </p>
        <el-table
          border
          v-if="currentPreview.kind === 'csv'"
          :data="currentPreview.rows ?? []"
          size="small"
          height="420"
          @header-dragend="onPreviewDragEnd"
        >
          <el-table-column
            v-for="(header, index) in currentPreview.headers"
            :key="index"
            :label="header"
            :width="previewWidth(header)"
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

/* 容器状态：四个等宽统计块 */
.stat-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3);
}

.stat {
  padding: var(--space-3) var(--space-4);
  background: var(--surface-2);
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--primary);
}

.stat__label {
  display: block;
  color: var(--text-muted);
  font-size: 12px;
  line-height: 18px;
}

.stat__value {
  display: block;
  margin-top: 6px;
  color: var(--text);
  font-size: 22px;
  line-height: 28px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.stat__value.is-on {
  color: var(--success);
}

.stat__value.is-off {
  color: var(--danger);
}

.stat__value.is-busy {
  color: var(--info);
}

.stat__note {
  display: block;
  margin-top: 6px;
  color: var(--text-faint);
  font-size: 12px;
  line-height: 18px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.stat-alert {
  margin: var(--space-3) 0 0;
  color: var(--danger);
  font-size: 12.5px;
}

@media (max-width: 1023px) {
  .stat-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 639px) {
  .stat-row {
    grid-template-columns: minmax(0, 1fr);
  }
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
  grid-template-columns: 132px 1fr;
  gap: 10px 16px;
  margin: 0;
}

.kv--four {
  grid-template-columns: 132px minmax(140px, 1fr) 132px 1fr;
}

.kv dt {
  color: var(--text-muted);
  font-size: 13.5px;
  line-height: 21px;
}

.kv dd {
  margin: 0;
  overflow-wrap: anywhere;
}

.library-preview {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(148px, 1fr));
  gap: 2px 16px;
  max-height: 216px;
  overflow: auto;
  padding: 12px 14px;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  color: var(--text);
  font-size: 12px;
  line-height: 20px;
}

.library-preview span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.facts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 16px 24px;
}

.fact {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.fact__label {
  color: var(--text-muted);
  font-size: 12px;
  line-height: 18px;
}

.fact__value {
  color: var(--text);
  font-size: 14px;
  line-height: 20px;
  overflow-wrap: anywhere;
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
