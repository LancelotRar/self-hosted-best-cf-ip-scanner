<script setup lang="ts">
import {
  CopyDocument,
  Download,
  FolderOpened,
  Refresh,
  View,
} from "@element-plus/icons-vue";
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import { get } from "../api";
import EmptyState from "../components/EmptyState.vue";
import ErrorState from "../components/ErrorState.vue";
import PageHeader from "../components/PageHeader.vue";
import type { OutputFile } from "../types";
import { formatSize, formatTime } from "../utils/format";

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

const files = ref<OutputFile[]>([]);
const readAt = ref("");
const loading = ref(false);
const error = ref("");
const activeTab = ref("all");
const previewVisible = ref(false);
const previewLoading = ref(false);
const current = ref<Preview | null>(null);
const copyVisible = ref(false);
const copyText = ref("");

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
  previewVisible.value = true;
  previewLoading.value = true;
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
    const text = data.content ?? "";
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      ElMessage.success("已复制订阅内容");
      return;
    }
    copyText.value = text;
    copyVisible.value = true;
  } catch (exception) {
    ElMessage.error((exception as Error).message);
  }
}

onMounted(load);
</script>

<template>
  <section class="page">
    <PageHeader
      title="产物"
      subtitle="TXT / CSV 预览、下载与订阅复制"
      :icon="FolderOpened"
    >
      <span v-if="readAt" class="muted">本次读取 {{ formatTime(readAt) }}</span>
      <el-button :loading="loading" @click="load"><el-icon><Refresh /></el-icon>刷新</el-button>
    </PageHeader>

    <ErrorState v-if="error" :message="error" @retry="load" />

    <el-tabs v-model="activeTab">
      <el-tab-pane label="全部" name="all" />
      <el-tab-pane label="订阅列表" name="subscription" />
      <el-tab-pane label="明细表" name="detail" />
    </el-tabs>

    <section v-if="filtered.length" class="panel output-panel">
      <div class="panel__body">
    <el-table :data="filtered" size="small">
      <el-table-column prop="name" label="文件" min-width="200">
        <template #default="{ row }"><span class="mono">{{ row.name }}</span></template>
      </el-table-column>
      <el-table-column label="大小" width="110">
        <template #default="{ row }">{{ formatSize(row.size) }}</template>
      </el-table-column>
      <el-table-column label="修改时间" width="180">
        <template #default="{ row }">{{ formatTime(row.mtime) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="230">
        <template #default="{ row }">
          <el-button size="small" @click="openPreview(row)">
            <el-icon><View /></el-icon>预览
          </el-button>
          <el-button v-if="row.name.endsWith('.txt')" size="small" @click="copySubscription(row)">
            <el-icon><CopyDocument /></el-icon>复制
          </el-button>
          <a :href="`/api/outputs/${encodeURIComponent(row.name)}?download=true`">
            <el-button size="small" text><el-icon><Download /></el-icon>下载</el-button>
          </a>
        </template>
      </el-table-column>
    </el-table>
      </div>
    </section>
    <EmptyState
      v-else
      title="尚无产物"
      description="尚无产物（下一轮扫描成功后生成）"
      :action-label="error ? '重试' : ''"
      @action="load"
    />

    <el-drawer v-model="previewVisible" :title="current?.name ?? '预览'" size="60%">
      <el-skeleton v-if="previewLoading" :rows="8" animated />
      <template v-else-if="current">
        <p class="muted preview-meta">
          {{ formatSize(current.size) }} · {{ formatTime(current.mtime) }} · sha256
          <span class="mono">{{ current.sha256.slice(0, 12) }}…</span>
        </p>
        <el-table v-if="current.kind === 'csv'" :data="current.rows ?? []" size="small" height="420">
          <el-table-column
            v-for="(header, index) in current.headers"
            :key="index"
            :label="header"
            min-width="120"
          >
            <template #default="{ row }">{{ row[index] }}</template>
          </el-table-column>
        </el-table>
        <pre v-else-if="current.kind === 'text'" class="preview-text mono">{{ current.content }}</pre>
        <EmptyState v-else title="该类型不支持预览" description="请下载后查看" />
        <p v-if="current.truncated" class="muted">仅显示前 200 行。</p>
      </template>
    </el-drawer>

    <el-dialog v-model="copyVisible" title="复制订阅内容" width="min(720px, 92vw)">
      <p class="muted">当前环境不允许直接写剪贴板，请手动复制：</p>
      <el-input v-model="copyText" type="textarea" :rows="12" readonly class="mono" />
    </el-dialog>
  </section>
</template>

<style scoped>
.output-panel {
  margin-top: var(--space-2);
}

.preview-meta {
  margin: 0 0 var(--space-3);
  font-size: 12px;
}

.preview-text {
  max-height: 460px;
  overflow: auto;
  margin: 0;
  padding: var(--space-3);
  background: var(--surface-2);
  border-radius: var(--radius-sm);
  font-size: 12px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
