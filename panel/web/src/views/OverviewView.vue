<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import {
  CircleCheck,
  DataLine,
  Download,
  FolderOpened,
  Monitor,
  Refresh,
  Timer,
  Upload,
  VideoPlay,
  Warning,
} from "@element-plus/icons-vue";

import { get } from "../api";
import EmptyState from "../components/EmptyState.vue";
import ErrorState from "../components/ErrorState.vue";
import PageHeader from "../components/PageHeader.vue";
import StatusPill from "../components/StatusPill.vue";
import type { OutputFile, Overview, OverviewPublish, OverviewSchedule } from "../types";
import {
  formatCount,
  formatDuration,
  formatMinute,
  formatSize,
  formatTime,
  triggerLabel,
} from "../utils/format";
import { runLabel, runQualified, runSummary, runTone } from "../utils/run";

interface Preview {
  name: string;
  kind: "text" | "csv" | "binary";
  size: number;
  mtime: string;
  sha256: string;
  content?: string;
  headers?: string[];
  rows?: string[][];
  row_count?: number | null;
  truncated?: boolean;
}

const router = useRouter();
const loading = ref(true);
const refreshing = ref(false);
const error = ref("");
const overview = ref<Overview | null>(null);


const previewVisible = ref(false);
const previewLoading = ref(false);
const currentPreview = ref<Preview | null>(null);
const previewFile = ref<OutputFile | null>(null);
const now = ref(Date.now());

const timezone = computed(
  () => overview.value?.timezone ?? overview.value?.schedule?.tz ?? "UTC",
);
const schedule = computed<OverviewSchedule>(
  () =>
    overview.value?.schedule ?? {
      cron: "",
      tz: timezone.value,
      enabled: false,
      next_runs: overview.value?.next_runs ?? [],
    },
);
const publish = computed<OverviewPublish>(
  () =>
    overview.value?.publish ?? {
      enabled: false,
      repo_url: null,
      branch: null,
      subdir: null,
      last: null,
    },
);
const recentRuns = computed(() => overview.value?.recent_runs ?? []);
const scannerOnline = computed(() => overview.value?.scanner.state === "running");
const lastRun = computed(() => overview.value?.last_run ?? null);
const qualified = computed(() => overview.value?.artifacts?.qualified ?? null);
const files = computed<OutputFile[]>(() =>
  (overview.value?.artifacts?.files ?? [])
    .filter((file) => /\.txt$/i.test(file.name))
    .sort((left, right) => {
      const a = listOrder(left.name);
      const b = listOrder(right.name);
      return (
        a[0] - b[0] ||
        a[1].localeCompare(b[1]) ||
        a[2] - b[2] ||
        left.name.localeCompare(right.name)
      );
    }),
);
const detailFile = computed<OutputFile | null>(
  () =>
    overview.value?.artifacts?.detail ??
    overview.value?.artifacts?.files?.find((file) => /\.csv$/i.test(file.name)) ??
    null,
);
const nextRun = computed(() => schedule.value.next_runs[0] ?? null);
const updatedAt = computed(() => overview.value?.artifacts?.updated_at ?? null);

/** 容器已运行时长：分钟级即可，超过一天用 d/h。 */
function uptimeText(started?: string | null): string {
  if (!started) return "—";
  const start = new Date(started).getTime();
  if (Number.isNaN(start)) return "—";
  const minutes = Math.max(0, Math.floor((now.value - start) / 60_000));
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
  if (!image) return "镜像未知";
  return image.split("/").pop() || image;
});

const lastRunMeta = computed(() => {
  if (!lastRun.value) return "暂无运行记录";
  return `${runLabel(lastRun.value)} · ${formatMinute(lastRun.value.finished_at ?? lastRun.value.started_at, timezone.value)}`;
});

const qualifiedMeta = computed(() => {
  if (qualified.value === null) return "尚无明细表";
  return `明细表 ${formatCount(qualified.value)} 行 · 更新于 ${formatMinute(updatedAt.value, timezone.value)}`;
});

const countdown = computed(() => {
  if (!nextRun.value) return "未安排下一次";
  const target = new Date(nextRun.value).getTime();
  if (Number.isNaN(target)) return "时间格式异常";
  const minutes = Math.round((target - now.value) / 60_000);
  if (minutes <= 0) return "即将执行";
  if (minutes < 60) return `还有 ${minutes} 分钟`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours < 24) return rest ? `还有 ${hours} 小时 ${rest} 分` : `还有 ${hours} 小时`;
  return `还有 ${Math.floor(hours / 24)} 天 ${hours % 24} 小时`;
});

const publishLast = computed(() => publish.value.last);
const publishLabel = computed(() => {
  if (!publish.value.enabled) return "已关闭";
  if (!publishLast.value) return "等待首次推送";
  return publishLast.value.publish_exit === 0 ? "推送成功" : "推送失败";
});
const publishTone = computed(() => {
  if (!publish.value.enabled) return "neutral" as const;
  if (!publishLast.value) return "info" as const;
  return publishLast.value.publish_exit === 0 ? ("success" as const) : ("warning" as const);
});

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

/** 产物排序：全量列表在前，国家列表随后，其他文本列表最后。 */
function listOrder(name: string): [number, string, number] {
  const global = /^GLOBAL(\d+)\.txt$/i.exec(name);
  if (global) return [0, "", Number(global[1])];
  const country = /^([A-Z]{2})(\d+)\.txt$/i.exec(name);
  if (country) return [1, country[1].toUpperCase(), Number(country[2])];
  return [2, name.toLowerCase(), 0];
}

function startText(value: string | null): string {
  return value ? formatMinute(value, timezone.value) : "—";
}

async function load(silent = false) {
  if (!silent) loading.value = true;
  else refreshing.value = true;
  error.value = "";
  try {
    overview.value = await get<Overview>("/api/overview");
  } catch (exception) {
    if (!silent) error.value = (exception as Error).message || "读取总览失败";
  } finally {
    loading.value = false;
    refreshing.value = false;
  }
}

async function openPreview(file: OutputFile) {
  previewFile.value = file;
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

function download(file: OutputFile) {
  const link = document.createElement("a");
  link.href = `/api/outputs/${encodeURIComponent(file.name)}?download=true`;
  link.download = file.name;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

function downloadCurrent() {
  if (previewFile.value) download(previewFile.value);
}

function openDetail() {
  if (detailFile.value) void openPreview(detailFile.value);
}

let timer: number | undefined;

onMounted(() => {
  void load();
  timer = window.setInterval(() => {
    now.value = Date.now();
    if (document.visibilityState === "visible") void load(true);
  }, 30_000);
  document.addEventListener("visibilitychange", onVisible);
});

function onVisible() {
  if (document.visibilityState === "visible") {
    now.value = Date.now();
    void load(true);
  }
}

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer);
  document.removeEventListener("visibilitychange", onVisible);
});
</script>

<template>
  <section class="page">
    <PageHeader
      title="信息总览"
      subtitle="扫描器、计划、运行、产物与推送情况的综合视图"
    >
      <template #actions>
        <el-button :loading="refreshing" @click="load(true)">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
      </template>
    </PageHeader>

    <ErrorState v-if="error" :message="error" @retry="load()" />
    <el-skeleton v-else-if="loading" :rows="8" animated />

    <div v-else-if="overview" class="overview">
      <!-- 离线不是一句吊在卡片外的红字：给出原因和下一步 -->
      <section v-if="!scannerOnline" class="health-alert" role="alert">
        <span class="health-alert__icon" aria-hidden="true"><el-icon><Warning /></el-icon></span>
        <div class="health-alert__text">
          <strong>扫描器当前不可用</strong>
          <p>{{ overview.scanner.reason || "面板无法连接扫描容器" }}</p>
        </div>
        <div class="health-alert__actions">
          <el-button size="small" @click="load()">重新检测</el-button>
          <el-button size="small" @click="router.push({ name: 'settings', query: { tab: 'container' } })">
            容器设置
          </el-button>
        </div>
      </section>

      <!-- 1. 运行状态：四张等宽指标卡 -->
      <section class="block">
        <header class="block__head">
          <el-icon><Monitor /></el-icon><span>运行状态</span>
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
              <template v-if="scannerOnline">运行 {{ uptime }} · </template>{{ imageLabel }}
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
              <span class="stat__icon"><el-icon><CircleCheck /></el-icon></span>
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
            <span class="stat__meta truncate">{{ lastRun ? startText(lastRun.finished_at ?? lastRun.started_at) : "暂无运行记录" }}</span>
          </article>

          <article class="stat" :class="qualified !== null ? 'stat--info' : 'stat--neutral'">
            <div class="stat__top">
              <span class="stat__icon"><el-icon><DataLine /></el-icon></span>
              <span class="stat__label">合格候选</span>
            </div>
            <strong class="stat__value" :class="qualified !== null ? 'is-busy' : ''">
              {{ formatCount(qualified) }}
            </strong>
            <span class="stat__meta truncate">{{ qualifiedMeta }}</span>
          </article>
        </div>
      </section>

      <!-- 2. 计划详情 + 推送情况 -->
      <div class="overview-split">
        <section class="block">
          <header class="block__head">
            <el-icon><Timer /></el-icon><span>计划详情</span>
            <button type="button" class="link-action" @click="router.push({ name: 'config', query: { tab: 'schedule' } })">
              修改
            </button>
          </header>
          <div class="panel block__card info-card">
            <div class="info-grid">
              <div class="info-fact">
                <span class="info-label">计划任务</span>
                <strong class="info-value">{{ describeCron(schedule.cron) }}</strong>
              </div>
              <div class="info-fact">
                <span class="info-label">下一次运行</span>
                <strong class="info-value mono">{{ formatTime(nextRun, timezone) }}</strong>
              </div>
              <div class="info-fact">
                <span class="info-label">倒计时</span>
                <strong class="info-value">{{ countdown }}</strong>
              </div>
              <div class="info-fact">
                <span class="info-label">时区</span>
                <strong class="info-value mono">{{ timezone }}</strong>
              </div>
            </div>
          </div>
        </section>

        <section class="block">
          <header class="block__head">
            <el-icon><Upload /></el-icon><span>推送情况</span>
            <button type="button" class="link-action" @click="router.push({ name: 'config', query: { tab: 'publish' } })">
              修改
            </button>
          </header>
          <div class="panel block__card info-card">
            <div class="info-grid">
              <div class="info-fact">
                <span class="info-label">推送状态</span>
                <StatusPill :tone="publishTone" :label="publishLabel" />
              </div>
              <div class="info-fact">
                <span class="info-label">上次推送时间</span>
                <strong class="info-value mono">
                  {{ publish.enabled && publishLast ? formatTime(publishLast.finished_at, timezone) : "—" }}
                </strong>
              </div>
              <div class="info-fact">
                <span class="info-label">目标仓库</span>
                <strong class="info-value mono">
                  {{ publish.repo_url || "—" }}
                </strong>
              </div>
              <div class="info-fact">
                <span class="info-label">分支与目录</span>
                <strong class="info-value mono">
                  {{ publish.branch || "—" }} / {{ publish.subdir || "—" }}
                </strong>
              </div>
            </div>
          </div>
        </section>
      </div>

      <!-- 3. 优选 IP 列表 -->
      <section class="block">
        <header class="block__head">
          <el-icon><FolderOpened /></el-icon><span>优选 IP 列表</span>
          <span class="block__meta">{{ files.length }} 个列表</span>
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
          <p v-if="files.length" class="table-hint">左右滑动查看全部列</p>
          <el-table
            v-if="files.length"
            border
            table-layout="fixed"
            :data="files"
            size="small"
            max-height="420"
            class="scroll-table overview-table"
          >
            <el-table-column
              label="文件"
              align="center"
              header-align="center"
              show-overflow-tooltip
            >
              <template #default="{ row }"><span class="mono">{{ row.name }}</span></template>
            </el-table-column>
            <el-table-column
              label="数量"
              align="center"
              header-align="center"
            >
              <template #default="{ row }"><span class="num">{{ formatCount(row.count) }}</span></template>
            </el-table-column>
            <el-table-column
              label="大小"
              align="center"
              header-align="center"
            >
              <template #default="{ row }"><span class="num">{{ formatSize(row.size) }}</span></template>
            </el-table-column>
            <el-table-column
              label="修改时间"
              align="center"
              header-align="center"
            >
              <template #default="{ row }"><span class="mono">{{ formatTime(row.mtime, timezone) }}</span></template>
            </el-table-column>
            <el-table-column
              label="操作"
              align="center"
              header-align="center"
            >
              <template #default="{ row }">
                <el-button text size="small" @click="openPreview(row)">预览</el-button>
                <el-button text size="small" @click="download(row)">下载</el-button>
              </template>
            </el-table-column>
          </el-table>
          <EmptyState
            v-else
            compact
            title="尚无优选 IP 列表"
            description="下一轮扫描成功后生成全量与国家列表"
          />
        </div>
      </section>

      <!-- 4. 近期扫描情况：只展示最近 10 次 -->
      <section class="block">
        <header class="block__head">
          <el-icon><VideoPlay /></el-icon><span>近期扫描情况</span>
          <span class="block__meta">最近 10 次</span>
          <button type="button" class="link-action" @click="router.push({ name: 'runs' })">
            查看全部
          </button>
        </header>
        <div class="panel block__card">
          <p v-if="recentRuns.length" class="table-hint">左右滑动查看全部列</p>
          <el-table
            v-if="recentRuns.length"
            border
            table-layout="fixed"
            :data="recentRuns"
            size="small"
            max-height="300"
            class="scroll-table overview-table"
          >
            <el-table-column
              label="开始时间"
              align="center"
              header-align="center"
            >
              <template #default="{ row }">
                <span class="mono">{{ startText(row.started_at) }}</span>
              </template>
            </el-table-column>
            <el-table-column
              label="触发器"
              align="center"
              header-align="center"
            >
              <template #default="{ row }">{{ triggerLabel(row.trigger) }}</template>
            </el-table-column>
            <el-table-column
              label="状态"
              align="center"
              header-align="center"
            >
              <template #default="{ row }">
                <StatusPill :tone="runTone(row)" :label="runLabel(row)" />
              </template>
            </el-table-column>
            <el-table-column
              label="合格"
              align="center"
              header-align="center"
            >
              <template #default="{ row }">
                <span class="num">{{ formatCount(runQualified(row)) }}</span>
              </template>
            </el-table-column>
            <el-table-column
              label="耗时"
              align="center"
              header-align="center"
            >
              <template #default="{ row }"><span class="num">{{ formatDuration(row.duration_s) }}</span></template>
            </el-table-column>
            <el-table-column
              label="摘要"
              align="center"
              header-align="center"
              show-overflow-tooltip
            >
              <template #default="{ row }"><span class="muted">{{ runSummary(row) }}</span></template>
            </el-table-column>
          </el-table>
          <EmptyState
            v-else
            compact
            title="尚无扫描记录"
            description="计划任务或手动触发完成后显示在这里"
            action-label="立即运行"
            @action="router.push({ name: 'runs' })"
          />
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
        <div class="preview-meta">
          <p class="section-note">
            {{ formatSize(currentPreview.size) }} · {{ formatTime(currentPreview.mtime, timezone) }}
            <template v-if="currentPreview.row_count != null"> · {{ formatCount(currentPreview.row_count) }} 行</template>
          </p>
          <el-button size="small" :disabled="!previewFile" @click="downloadCurrent">
            <el-icon><Download /></el-icon>下载
          </el-button>
        </div>
        <p v-if="currentPreview.truncated" class="preview-note">
          仅显示前 {{ currentPreview.rows?.length ?? 200 }} 行，完整内容请下载。
        </p>
        <el-table
          v-if="currentPreview.kind === 'csv'"
          border
          :data="currentPreview.rows ?? []"
          size="small"
          max-height="420"
        >
          <el-table-column
            v-for="(header, index) in currentPreview.headers"
            :key="index"
            :label="header"
            min-width="140"
          >
            <template #default="{ row }">{{ row[index] }}</template>
          </el-table-column>
        </el-table>
        <pre v-else-if="currentPreview.kind === 'text'" class="dialog-preview mono">{{
          currentPreview.content
        }}</pre>
        <EmptyState v-else compact title="该类型不支持预览" description="请下载后查看" />
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
  margin-left: auto;
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

/* 离线横幅：原因、重新检测、容器设置都在同一处 */
.health-alert {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: 14px 16px;
  border: 1px solid color-mix(in srgb, var(--danger) 40%, var(--border));
  border-radius: var(--radius-md);
  background: var(--tone-danger-soft);
}

.health-alert__icon {
  display: inline-grid;
  place-items: center;
  flex: 0 0 auto;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  color: var(--danger);
  background: color-mix(in srgb, var(--danger) 14%, var(--surface));
}

.health-alert__text {
  min-width: 0;
  flex: 1;
}

.health-alert__text strong {
  font-size: var(--fs-body);
}

.health-alert__text p {
  margin: 2px 0 0;
  color: var(--text-muted);
  font-size: var(--fs-meta);
  line-height: 18px;
  overflow-wrap: anywhere;
}

.health-alert__actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  padding-top: 2px;
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
  min-height: 132px;
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

/* 计划 / 推送：两张等宽信息卡，2×2 事实网格 */
.overview-split {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-5);
  align-items: stretch;
}

.overview-split .block {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.overview-split .info-card {
  flex: 1;
}

.info-card {
  padding: 18px 24px;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px 28px;
}

.info-fact {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  min-width: 0;
}

.info-label {
  color: var(--text-muted);
  font-size: var(--fs-meta);
  line-height: 18px;
}

.info-value {
  min-width: 0;
  color: var(--text);
  font-size: var(--fs-body);
  line-height: 20px;
  font-weight: 600;
  text-align: left;
  overflow-wrap: anywhere;
}

.table-hint {
  display: none;
  margin: 0 0 var(--space-2);
  color: var(--text-faint);
  font-size: var(--fs-micro);
  line-height: 16px;
  text-align: center;
}

.preview-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.section-note {
  margin: 0;
  color: var(--text-muted);
  font-size: var(--fs-meta);
  line-height: 18px;
}

.preview-note {
  margin: 0 0 var(--space-2);
  color: var(--warning);
  font-size: var(--fs-meta);
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

@media (max-width: 1199px) {
  .stat-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
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
    min-height: 118px;
    padding: 14px 16px 12px;
  }

  .stat__value {
    font-size: 21px;
    line-height: 28px;
  }

  .health-alert {
    flex-wrap: wrap;
  }

  .health-alert__actions {
    width: 100%;
    padding-left: 42px;
  }

  .info-card {
    padding: var(--space-4) var(--space-4) var(--space-5);
  }

  .info-grid {
    grid-template-columns: minmax(0, 1fr);
    gap: var(--space-4);
  }

  .overview-table {
    min-width: 900px;
  }

  .table-hint {
    display: block;
  }
}

@media (max-width: 359px) {
  .stat-row {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
