<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import { get } from "../api";
import EmptyState from "../components/EmptyState.vue";
import type { OutputFile } from "../types";

interface Preview {
  name: string;
  kind: "text" | "csv" | "binary";
  size: number;
  mtime: string;
  sha256: string;
  content?: string;
  headers?: string[];
  rows?: string[][];
  line_count?: number;
  truncated?: boolean;
}

const files = ref<OutputFile[]>([]);
const readAt = ref("");
const loading = ref(false);
const error = ref("");
const activeTab = ref("all");
const previewVisible = ref(false);
const current = ref<Preview | null>(null);
const previewLoading = ref(false);

const filtered = computed(() => {
  if (activeTab.value === "subscription") {
    return files.value.filter((file) => file.name.endsWith(".txt"));
  }
  if (activeTab.value === "detail") {
    return files.value.filter((file) => file.name.endsWith(".csv"));
  }
  return files.value;
});

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const data = await get<{ read_at: string; files: OutputFile[] }>("/api/outputs");
    files.value = data.files;
    readAt.value = data.read_at;
  } catch (exception) {
    error.value = (exception as Error).message;
    files.value = [];
  } finally {
    loading.value = false;
  }
}

async function openPreview(file: OutputFile) {
  previewLoading.value = true;
  previewVisible.value = true;
  current.value = null;
  try {
    current.value = await get<Preview>(`/api/outputs/${encodeURIComponent(file.name)}`);
  } catch (exception) {
    ElMessage.error((exception as Error).message);
    previewVisible.value = false;
  } finally {
    previewLoading.value = false;
  }
}

async function copySubscription(file: OutputFile) {
  try {
    const data = await get<Preview>(`/api/outputs/${encodeURIComponent(file.name)}`);
    await navigator.clipboard.writeText(data.content ?? "");
    ElMessage.success("已复制订阅内容");
  } catch (exception) {
    ElMessage.error((exception as Error).message);
  }
}

function formatTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false });
}

function formatSize(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

onMounted(load);
</script>

<template>
  <section class="panel-page">
    <div class="panel-page__title">
      <h1>产物</h1>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </div>

    <p class="panel-muted" v-if="readAt">本次读取：{{ formatTime(readAt) }}</p>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false">
      <el-button size="small" @click="load">重试</el-button>
    </el-alert>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="全部" name="all" />
      <el-tab-pane label="订阅列表" name="subscription" />
      <el-tab-pane label="明细表" name="detail" />
    </el-tabs>

    <el-table v-if="filtered.length" :data="filtered" size="small">
      <el-table-column prop="name" label="文件" />
      <el-table-column label="大小" width="110">
        <template #default="{ row }">{{ formatSize(row.size) }}</template>
      </el-table-column>
      <el-table-column label="修改时间" width="200">
        <template #default="{ row }">{{ formatTime(row.mtime) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="240">
        <template #default="{ row }">
          <el-button size="small" @click="openPreview(row)">预览</el-button>
          <el-button size="small" @click="copySubscription(row)" v-if="row.name.endsWith('.txt')">
            复制
          </el-button>
          <a :href="`/api/outputs/${encodeURIComponent(row.name)}?download=true`">
            <el-button size="small" text>下载</el-button>
          </a>
        </template>
      </el-table-column>
    </el-table>
    <EmptyState
      v-else
      title="尚无产物"
      description="尚无产物（下一轮扫描成功后生成）"
      :retry-label="error ? '重试' : ''"
      @retry="load"
    />

    <el-drawer v-model="previewVisible" :title="current?.name ?? '预览'" size="60%">
      <el-skeleton v-if="previewLoading" :rows="8" animated />
      <template v-else-if="current">
        <p class="panel-muted">
          {{ formatSize(current.size) }} · {{ formatTime(current.mtime) }} · sha256
          <span class="panel-mono">{{ current.sha256.slice(0, 12) }}…</span>
        </p>
        <el-table v-if="current.kind === 'csv'" :data="current.rows ?? []" size="small" height="420">
          <el-table-column
            v-for="(header, index) in current.headers"
            :key="index"
            :label="header"
            :prop="String(index)"
          >
            <template #default="{ row }">{{ row[index] }}</template>
          </el-table-column>
        </el-table>
        <pre v-else-if="current.kind === 'text'" class="panel-mono preview">{{ current.content }}</pre>
        <el-empty v-else description="该类型不支持预览，请下载查看" />
        <p class="panel-muted" v-if="current.truncated">仅显示前 200 行。</p>
      </template>
    </el-drawer>
  </section>
</template>

<style scoped>
.preview {
  max-height: 420px;
  overflow: auto;
  padding: 12px;
  background: var(--panel-bg);
  border-radius: 8px;
}
</style>
