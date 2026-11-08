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
import type { OutputFile, Overview, Param, RunRecord } from "../types";
import {
  exitLabel,
  formatCount,
  formatDuration,
  formatMinute,
  formatSize,
  formatTime,
  triggerLabel,
} from "../utils/format";

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
const detailFile = ref<OutputFile | null>(null);
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

/** 镜像名太长，卡片主值只放仓库名与标签；完整地址放到 title。 */
const imageLabel = computed(() => {
  const image = overview.value?.scanner.image ?? "";
  if (!image) return "—";
  return image.split("/").pop() || image;
});

function paramValue(name: string): unknown {
  return publish.value?.params.find((param) => param.name === name)?.value;
}

const pushEnabled = () => paramValue("GIT_PUSH_ENABLED") === true;

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [ov, history, outputs, pub, config] = await Promise.all([
      get<Overview>("/api/overview"),
      get<{ runs: RunRecord[] }>("/api/runs?limit=10"),
      get<{ read_at: string; files: OutputFile[] }>("/api/outputs"),
      get<PublishResponse>("/api/publish"),
      get<{ params: Param[] }>("/api/config"),
    ]);
    overview.value = ov;
    runs.value = history.runs;
    files.value = sortOutputs(outputs.files.filter((file) => /\.txt$/i.test(file.name)));
    detailFile.value = outputs.files.find((file) => /\.csv$/i.test(file.name)) ?? null;
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

function runLabel(record: RunRecord): string {
  if (record.status === "running") return "运行中";
  if (record.status === "interrupted") return "中断";
  if (record.status === "done" || (!record.status && record.finished_at)) {
    return typeof record.scan_exit === "number" && record.scan_exit !== 0 ? "失败" : "完成";
  }
  return "—";
}

function runTone(record: RunRecord): "success" | "warning" | "info" | "neutral" {
  if (record.status === "running") return "info";
  if (record.status === "interrupted") return "warning";
  if (record.status === "done" || (!record.status && record.finished_at)) {
    return typeof record.scan_exit === "number" && record.scan_exit !== 0 ? "warning" : "success";
  }
  return "neutral";
}

const lastRun = computed<RunRecord | null>(() => overview.value?.last_run ?? runs.value[0] ?? null);

const lastRunMeta = computed(() => {
  const record = lastRun.value;
  if (!record) return "暂无运行记录";
  const duration = formatDuration(record.duration_s);
  return duration === "—" ? triggerLabel(record.trigger) : `${duration} · ${triggerLabel(record.trigger)}`;
});

const uptimeMeta = computed(() => {
  const started = overview.value?.scanner.started_at;
  return started ? `自 ${formatMinute(started)} 起` : "容器未运行";
});

/** 开始时间按分钟展示；缺失记录时从 run_id（`YYYYMMDDTHHMMSS-序号`）回退解析。 */
function startText(record: RunRecord): string {
  if (record.started_at) return formatMinute(record.started_at);
  const match = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})/.exec(record.run_id);
  if (!match) return record.run_id;
  const [, year, month, day, hour, minute] = match;
  return `${year}-${month}-${day} ${hour}:${minute}`;
}

/** 产物排序：全量列表在前，国家列表随后，其他文本列表与明细表最后。 */
function listOrder(name: string): [number, string, number] {
  const global = /^GLOBAL(\d+)\.txt$/i.exec(name);
  if (global) return [0, "", Number(global[1])];
  const country = /^([A-Z]{2})(\d+)\.txt$/i.exec(name);
  if (country) return [1, country[1].toUpperCase(), Number(country[2])];
  if (/\.txt$/i.test(name)) return [2, name.toLowerCase(), 0];
  return [3, name.toLowerCase(), 0];
}

function sortOutputs(rows: OutputFile[]): OutputFile[] {
  return [...rows].sort((left, right) => {
    const a = listOrder(left.name);
    const b = listOrder(right.name);
    return (
      a[0] - b[0] ||
      a[1].localeCompare(b[1]) ||
      a[2] - b[2] ||
      left.name.localeCompare(right.name)
    );
  });
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

function openDetail() {
  if (detailFile.value) void openPreview(detailFile.value);
}

onMounted(load);
</script>

<template>
  <section class="page">
    <PageHeader
      title="信息总览"
      subtitle="扫描器、计划、运行、产物与推送情况的综合视图"
    />

    <ErrorState v-if="error" :message="error" @retry="load" />
    <el-skeleton v-else-if="loading" :rows="8" animated />

    <div v-else-if="overview" class="overview">
      <!-- 1. 容器状态：四张等宽指标卡 -->
      <section class="block">
        <header class="block__head">
          <el-icon><Monitor /></el-icon><span>容器状态</span>
          <span class="block__meta">每 30 秒自动刷新</span>
        </header>
        <div class="stat-row">
          <article class="stat" :class="scannerOnline ? 'stat--success' : 'stat--danger'">
            <div class="stat__top">
              <span class="stat__icon"><el-icon><Monitor /></el-icon></span>
              <span class="stat__label">扫描容器</span>
            </div>
            <strong class="stat__value" :class="scannerOnline ? 'is-on' : 'is-off'">
              {{ scannerOnline ? "在线" : "离线" }}
            </strong>
            <span class="stat__meta truncate" :title="overview.scanner.image ?? ''">
              {{ imageLabel === "—" ? "镜像未知" : imageLabel }}
            </span>
          </article>

          <article class="stat" :class="overview.running ? 'stat--info' : 'stat--neutral'">
            <div class="stat__top">
              <span class="stat__icon"><el-icon><VideoPlay /></el-icon></span>
              <span class="stat__label">当前任务</span>
            </div>
            <strong class="stat__value" :class="overview.running ? 'is-busy' : ''">
              {{ overview.running ? "运行中" : "空闲" }}
            </strong>
            <span class="stat__meta truncate">
              {{ overview.running ? "正在执行本轮扫描" : lastRunMeta }}
            </span>
          </article>

          <article
            class="stat"
            :class="
              lastRun
                ? runTone(lastRun) === 'success'
                  ? 'stat--success'
                  : 'stat--warning'
                : 'stat--neutral'
            "
          >
            <div class="stat__top">
              <span class="stat__icon"><el-icon><DataLine /></el-icon></span>
              <span class="stat__label">最近一轮</span>
            </div>
            <strong
              class="stat__value"
              :class="
                lastRun
                  ? runTone(lastRun) === 'success'
                    ? 'is-on'
                    : runTone(lastRun) === 'warning'
                      ? 'is-failed'
                      : ''
                  : ''
              "
            >
              {{ lastRun ? runLabel(lastRun) : "—" }}
            </strong>
            <span class="stat__meta truncate">
              {{ lastRun ? startText(lastRun) : "暂无运行记录" }}
            </span>
          </article>

          <article class="stat stat--neutral">
            <div class="stat__top">
              <span class="stat__icon"><el-icon><Timer /></el-icon></span>
              <span class="stat__label">已运行</span>
            </div>
            <strong class="stat__value">{{ uptime }}</strong>
            <span class="stat__meta truncate">{{ uptimeMeta }}</span>
          </article>
        </div>

        <p v-if="overview.scanner.reason" class="stat-alert">
          离线原因：{{ overview.scanner.reason }}
        </p>
      </section>

      <!-- 2. 计划详情 + 推送情况 -->
      <div class="overview-split">
        <section class="block">
          <header class="block__head">
            <el-icon><Timer /></el-icon><span>计划详情</span>
          </header>
          <div class="panel block__card info-card">
            <div class="info-row">
              <span class="info-label">计划任务</span>
              <strong class="info-value">{{ describeCron(cronExpression) }}</strong>
            </div>
            <div class="info-row">
              <span class="info-label">下一次运行</span>
              <strong class="info-value mono">{{ formatTime(overview.next_runs[0]) }}</strong>
            </div>
            <div class="info-row">
              <span class="info-label">时区</span>
              <strong class="info-value mono">{{ timezone || "—" }}</strong>
            </div>
            <div class="info-row">
              <span class="info-label">计划状态</span>
              <strong class="info-value" :class="cronExpression ? 'is-on' : 'is-off'">
                {{ cronExpression ? "已启用" : "未配置" }}
              </strong>
            </div>
          </div>
        </section>

        <section class="block">
          <header class="block__head">
            <el-icon><Upload /></el-icon><span>推送情况</span>
          </header>
          <div class="panel block__card info-card">
            <div class="info-row">
              <span class="info-label">推送状态</span>
              <strong class="info-value" :class="pushEnabled() ? 'is-on' : 'is-off'">
                {{ pushEnabled() ? "已开启" : "已关闭" }}
              </strong>
            </div>
            <div class="info-row">
              <span class="info-label">目标仓库</span>
              <strong class="info-value mono info-value--wrap">
                {{ paramValue("GIT_REPO_URL") || "—" }}
              </strong>
            </div>
            <div class="info-row">
              <span class="info-label">分支与目录</span>
              <strong class="info-value mono">
                {{ paramValue("GIT_BRANCH") || "—" }} /
                {{ paramValue("GIT_OUTPUT_SUBDIR") || "—" }}
              </strong>
            </div>
            <div class="info-row">
              <span class="info-label">上次推送时间</span>
              <strong class="info-value mono">
                {{ pushEnabled() && publish?.last ? formatTime(publish.last.finished_at) : "—" }}
              </strong>
            </div>
          </div>
        </section>
      </div>

      <!-- 3. 优选 IP 列表 -->
      <section class="block">
        <header class="block__head">
          <el-icon><FolderOpened /></el-icon><span>优选 IP 列表</span>
          <span class="block__meta">{{ files.length }} 个文件</span>
          <button
            type="button"
            class="link-action"
            :disabled="!detailFile"
            :title="detailFile ? '查看明细统计' : '暂无明细表'"
            @click="openDetail"
          >
            <el-icon aria-hidden="true"><DataLine /></el-icon>
            统计信息
          </button>
        </header>
        <div class="panel block__card">
          <el-table
            border
            v-if="files.length"
            :data="files"
            size="small"
            max-height="360"
            class="scroll-table"
            @header-dragend="onFilesDragEnd"
          >
            <el-table-column label="文件" :width="filesWidth('文件')" min-width="220" show-overflow-tooltip>
              <template #default="{ row }"><span class="mono">{{ row.name }}</span></template>
            </el-table-column>
            <el-table-column label="数量" :width="filesWidth('数量')" min-width="110" align="right">
              <template #default="{ row }"><span class="num">{{ formatCount(row.count) }}</span></template>
            </el-table-column>
            <el-table-column label="修改时间" :width="filesWidth('修改时间')" min-width="210">
              <template #default="{ row }"><span class="mono">{{ formatTime(row.mtime) }}</span></template>
            </el-table-column>
            <el-table-column label="预览" :width="filesWidth('预览')" min-width="110" align="center">
              <template #default="{ row }">
                <el-button text size="small" @click="openPreview(row)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>
          <EmptyState v-else title="尚无优选 IP 列表" description="下一轮扫描成功后生成全量与国家列表" />
        </div>
      </section>

      <!-- 4. 近期扫描情况：只展示最近 10 次 -->
      <section class="block">
        <header class="block__head">
          <el-icon><VideoPlay /></el-icon><span>近期扫描情况</span>
          <span class="block__meta">最近 10 次</span>
        </header>
        <div class="panel block__card">
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
            <el-table-column label="触发器" :width="runsWidth('触发器')" min-width="90" align="center">
              <template #default="{ row }">{{ triggerLabel(row.trigger) }}</template>
            </el-table-column>
            <el-table-column label="状态" :width="runsWidth('状态')" min-width="102" align="center">
              <template #default="{ row }">
                <StatusPill :tone="runTone(row)" :label="runLabel(row)" />
              </template>
            </el-table-column>
            <el-table-column label="扫描" :width="runsWidth('扫描')" min-width="115" align="center">
              <template #default="{ row }">{{ exitLabel(row.scan_exit) }}</template>
            </el-table-column>
            <el-table-column label="耗时" :width="runsWidth('耗时')" min-width="115" align="right">
              <template #default="{ row }"><span class="num">{{ formatDuration(row.duration_s) }}</span></template>
            </el-table-column>
          </el-table>
          <EmptyState v-else title="尚无扫描记录" description="计划任务或手动触发完成后显示在这里" />
        </div>
      </section>
    </div>

    <el-dialog
      v-model="previewVisible"
      :title="currentPreview?.name ?? '产物预览'"
      width="min(860px, 94vw)"
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
          max-height="420"
          @header-dragend="onPreviewDragEnd"
        >
          <el-table-column
            v-for="(header, index) in currentPreview.headers"
            :key="index"
            :label="header"
            :width="previewWidth(header)"
            min-width="140"
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
  gap: var(--space-6);
}

/* 区块标题右侧的轻量操作 */
.link-action {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  margin-left: 4px;
  border: 0;
  border-radius: var(--radius-xs);
  background: none;
  color: var(--text-faint);
  font-family: inherit;
  font-size: var(--fs-meta);
  line-height: 18px;
  cursor: pointer;
  transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease);
}

.link-action:hover:not(:disabled) {
  color: var(--text);
  background: var(--surface-2);
}

.link-action:disabled {
  cursor: default;
  opacity: 0.55;
}

/* 容器状态：四个等宽指标卡，中性底 + 语义色只用于图标与状态值 */
.stat-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
}

.stat {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 136px;
  padding: 18px 20px 16px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow);
}

.stat__top {
  display: flex;
  align-items: center;
  gap: 9px;
}

.stat__icon {
  display: inline-grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: var(--tone-neutral-soft);
  color: var(--text-muted);
  font-size: 15px;
}

.stat--success .stat__icon {
  background: var(--tone-success-soft);
  color: var(--success);
}

.stat--danger .stat__icon {
  background: var(--tone-danger-soft);
  color: var(--danger);
}

.stat--warning .stat__icon {
  background: var(--tone-warning-soft);
  color: var(--warning);
}

.stat--info .stat__icon {
  background: var(--tone-info-soft);
  color: var(--info);
}

.stat__label {
  color: var(--text-muted);
  font-size: var(--fs-meta);
  font-weight: 500;
  line-height: 18px;
}

.stat__value {
  margin-top: 6px;
  color: var(--text);
  font-size: 24px;
  line-height: 30px;
  font-weight: 650;
  letter-spacing: -0.022em;
  font-variant-numeric: tabular-nums;
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

.stat__value.is-failed {
  color: var(--warning);
}

.stat__meta {
  margin-top: auto;
  padding-top: 10px;
  color: var(--text-faint);
  font-size: var(--fs-meta);
  line-height: 18px;
}

.stat-alert {
  margin: 0;
  color: var(--danger);
  font-size: var(--fs-meta);
  line-height: 18px;
}

/* 计划 / 推送：两张等宽信息卡，四行对齐 */
.overview-split {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-5);
  align-items: start;
}

.overview-split .block {
  min-width: 0;
}

.info-card {
  padding: 8px 24px 10px;
}

.info-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-4);
  padding: 11px 0;
}

.info-row + .info-row {
  border-top: 1px solid var(--border-soft);
}

.info-label {
  flex: 0 0 auto;
  color: var(--text-muted);
  font-size: var(--fs-meta);
  line-height: 20px;
}

.info-value {
  min-width: 0;
  color: var(--text);
  font-size: var(--fs-body);
  line-height: 20px;
  font-weight: 600;
  text-align: right;
  overflow-wrap: anywhere;
}

.info-value--wrap {
  max-width: 64%;
}

.info-value.is-on {
  color: var(--success);
}

.info-value.is-off {
  color: var(--text-muted);
}

.section-note {
  margin: 0 0 var(--space-3);
  color: var(--text-muted);
  font-size: var(--fs-meta);
  line-height: 18px;
}

.dialog-preview {
  max-height: 440px;
  overflow: auto;
  margin: 0;
  padding: var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  font-size: var(--fs-meta);
  line-height: 18px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

@media (max-width: 1023px) {
  .stat-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .overview-split {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 639px) {
  .stat-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-3);
  }

  .stat {
    min-height: 122px;
    padding: 14px 16px 12px;
  }

  .stat__value {
    font-size: 21px;
    line-height: 28px;
  }
}

@media (max-width: 359px) {
  .stat-row {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
