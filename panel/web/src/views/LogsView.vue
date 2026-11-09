<script setup lang="ts">
import {
  Delete,
  Download,
  DocumentCopy,
  Search,
  VideoPause,
  VideoPlay,
  Warning,
} from "@element-plus/icons-vue";
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";

import { get } from "../api";
import EmptyState from "../components/EmptyState.vue";
import LogConsole from "../components/LogConsole.vue";
import PageHeader from "../components/PageHeader.vue";
import StatusPill from "../components/StatusPill.vue";
import { useEventStream } from "../composables/useEventStream";
import type { Overview } from "../types";
import { logLevelOf } from "../utils/format";

type LevelFilter = "all" | "错误" | "警告" | "信息";

const router = useRouter();
const filter = ref("");
const level = ref<LevelFilter>("all");
const lines = ref<string[]>([]);
const overview = ref<Overview | null>(null);
const timezone = ref("UTC");
const MAX_LINES = 5000;

const { status, lastReceived, connect, pause, resume } = useEventStream(
  () => "/api/logs/stream?tail=200",
  {
    onMessage: (data) => {
      lines.value.push(data);
      if (lines.value.length > MAX_LINES) {
        lines.value = lines.value.slice(-MAX_LINES);
      }
    },
  },
);

const levelCounts = computed(() => {
  let errors = 0;
  let warnings = 0;
  let info = 0;
  for (const line of lines.value) {
    const parsed = logLevelOf(line);
    if (parsed === "错误") errors += 1;
    else if (parsed === "警告") warnings += 1;
    else info += 1;
  }
  return { all: lines.value.length, 错误: errors, 警告: warnings, 信息: info };
});

const visible = computed(() => {
  const keyword = filter.value.trim();
  return lines.value.filter((line) => {
    if (level.value !== "all" && logLevelOf(line) !== level.value) return false;
    return keyword ? line.includes(keyword) : true;
  });
});

const paused = computed(() => status.value === "paused");
const scannerOnline = computed(() => overview.value?.scanner.state === "running");
const levelOptions: Array<{ value: LevelFilter; label: string }> = [
  { value: "all", label: "全部" },
  { value: "错误", label: "错误" },
  { value: "警告", label: "警告" },
  { value: "信息", label: "信息" },
];

function togglePause() {
  if (paused.value) resume();
  else pause();
}

function clear() {
  lines.value = [];
}

async function copyVisible() {
  const text = visible.value.join("\n");
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success(`已复制 ${visible.value.length} 行`);
  } catch {
    ElMessage.error("复制失败，请改用下载");
  }
}

function download() {
  const link = document.createElement("a");
  link.href = "/api/logs/download?tail=5000";
  link.download = "scanner-logs.txt";
  document.body.appendChild(link);
  link.click();
  link.remove();
}

onMounted(async () => {
  connect();
  try {
    overview.value = await get<Overview>("/api/overview");
    timezone.value = overview.value.timezone || "UTC";
  } catch {
    // 总览不可用时仍允许看日志；时区退回 UTC
  }
});
</script>

<template>
  <section class="page">
    <PageHeader
      title="查看日志"
      subtitle="本项目扫描容器的实时日志；断开时显示重连状态"
    />

    <section v-if="overview && !scannerOnline" class="log-alert" role="alert">
      <el-icon><Warning /></el-icon>
      <div>
        <strong>扫描器当前离线</strong>
        <p>{{ overview.scanner.reason || "面板无法连接扫描容器，日志连接会持续重试。" }}</p>
      </div>
      <el-button size="small" @click="router.push({ name: 'settings', query: { tab: 'container' } })">
        容器设置
      </el-button>
    </section>

    <div class="log-toolbar">
      <el-input v-model="filter" placeholder="关键字过滤" clearable class="filter">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <div class="filter-chips" role="group" aria-label="按日志等级筛选">
        <button
          v-for="option in levelOptions"
          :key="option.value"
          type="button"
          class="filter-chip"
          :class="{ 'filter-chip--active': level === option.value }"
          @click="level = option.value"
        >
          {{ option.label }}
          <span class="filter-chip__count">{{ levelCounts[option.value] }}</span>
        </button>
      </div>
      <span class="spacer" />
      <span class="muted log-count">显示 {{ visible.length }} / {{ lines.length }} 行</span>
      <el-button @click="togglePause">
        <el-icon>
          <VideoPlay v-if="paused" />
          <VideoPause v-else />
        </el-icon>
        {{ paused ? "继续" : "暂停" }}
      </el-button>
      <el-button :disabled="!visible.length" @click="copyVisible">
        <el-icon><DocumentCopy /></el-icon>复制
      </el-button>
      <el-button @click="clear"><el-icon><Delete /></el-icon>清空</el-button>
      <el-button @click="download"><el-icon><Download /></el-icon>下载</el-button>
    </div>

    <div class="log-status">
      <StatusPill
        :tone="status === 'live' ? 'success' : status === 'connecting' ? 'info' : status === 'paused' ? 'warning' : 'danger'"
        :label="status === 'live' ? '实时连接' : status === 'connecting' ? '连接中' : status === 'paused' ? '已暂停' : '已断开'"
        :pulse="status === 'connecting'"
      />
      <span class="muted">最多保留最近 {{ MAX_LINES }} 行；断线会自动重连。</span>
    </div>

    <LogConsole
      v-if="lines.length || status !== 'disconnected'"
      :lines="visible"
      :status="status"
      :last-received="lastReceived"
      :time-zone="timezone"
      height="480px"
    />
    <EmptyState
      v-else
      compact
      title="暂无日志连接"
      description="扫描器恢复后会自动重连，无需手动刷新；也可以先到容器设置检查服务状态。"
    />
  </section>
</template>

<style scoped>
.log-alert {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: 12px 14px;
  margin-bottom: var(--space-4);
  border: 1px solid color-mix(in srgb, var(--danger) 40%, var(--border));
  border-radius: var(--radius-md);
  background: var(--tone-danger-soft);
}

.log-alert > .el-icon {
  color: var(--danger);
  font-size: 18px;
  margin-top: 2px;
}

.log-alert strong {
  font-size: var(--fs-body);
}

.log-alert p {
  margin: 2px 0 0;
  color: var(--text-muted);
  font-size: var(--fs-meta);
  line-height: 18px;
  overflow-wrap: anywhere;
}

.log-alert .el-button {
  margin-left: auto;
}

.log-toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-bottom: var(--space-3);
}

.filter {
  width: min(300px, 100%);
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

.log-count {
  font-size: var(--fs-meta);
}

.log-status {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
  font-size: var(--fs-meta);
}

@media (max-width: 767px) {
  .filter {
    width: 100%;
  }

  .log-count {
    flex: 1 1 100%;
  }
}
</style>
