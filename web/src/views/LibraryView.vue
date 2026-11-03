<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { onBeforeRouteLeave } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";

import { get, post, put } from "../api";
import EmptyState from "../components/EmptyState.vue";
import type { LibraryDocument } from "../types";

interface BackupFile {
  name: string;
  size: number;
  mtime: string;
}

const activeTab = ref("edit");
const document = ref<LibraryDocument | null>(null);
const content = ref("");
const serverContent = ref("");
const error = ref("");
const lineErrors = ref<Array<{ line: number; message: string }>>([]);
const backups = ref<BackupFile[]>([]);
const loading = ref(false);
const saving = ref(false);

const dirty = computed(() => content.value !== serverContent.value);

function applyDocument(data: LibraryDocument) {
  document.value = data;
  content.value = data.content;
  serverContent.value = data.content;
  lineErrors.value = [];
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    applyDocument(await get<LibraryDocument>("/api/library"));
  } catch (exception) {
    error.value = (exception as Error).message;
  } finally {
    loading.value = false;
  }
}

async function loadBackups() {
  try {
    const data = await get<{ backups: BackupFile[] }>("/api/library/backups");
    backups.value = data.backups;
  } catch (exception) {
    ElMessage.error((exception as Error).message);
  }
}

async function save() {
  if (!document.value) return;
  saving.value = true;
  lineErrors.value = [];
  try {
    const result = await put<LibraryDocument>("/api/library", {
      hash: document.value.hash,
      content: content.value,
    });
    applyDocument(result);
    ElMessage.success("已保存地址库");
    await loadBackups();
  } catch (exception) {
    const failure = exception as Error & { details?: Array<{ line: number; message: string }> };
    if (Array.isArray(failure.details)) {
      lineErrors.value = failure.details.map((detail) => ({
        line: detail.line,
        message: detail.message ?? "无法解析",
      }));
    }
    ElMessage.error(failure.message);
  } finally {
    saving.value = false;
  }
}

function cancel() {
  content.value = serverContent.value;
  lineErrors.value = [];
}

async function restore(name: string) {
  try {
    await ElMessageBox.confirm(`用备份 ${name} 覆盖当前地址库？`, "恢复备份", {
      confirmButtonText: "恢复",
      cancelButtonText: "取消",
      type: "warning",
    });
  } catch {
    return;
  }
  try {
    applyDocument(await post<LibraryDocument>(`/api/library/backups/${encodeURIComponent(name)}/restore`));
    ElMessage.success("已恢复备份");
    await loadBackups();
  } catch (exception) {
    ElMessage.error((exception as Error).message);
  }
}

function formatTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false });
}

onMounted(async () => {
  await load();
  await loadBackups();
});

onBeforeRouteLeave(async () => {
  if (!dirty.value) return true;
  try {
    await ElMessageBox.confirm("地址库有未保存的修改，确定离开？", "未保存的修改", {
      confirmButtonText: "离开",
      cancelButtonText: "留下",
      type: "warning",
    });
    return true;
  } catch {
    return false;
  }
});
</script>

<template>
  <section class="panel-page">
    <div class="panel-page__title">
      <h1>IP 库</h1>
      <el-button :loading="loading" @click="load">重新加载</el-button>
    </div>

    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false">
      <el-button size="small" @click="load">重试</el-button>
    </el-alert>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="编辑" name="edit">
        <p class="panel-muted" v-if="document">
          {{ document.line_count }} 行 · 网段 {{ document.stats.networks }} · 固定条目
          {{ document.stats.fixed }} · 跳过 {{ document.stats.skipped }} · 修改时间
          {{ formatTime(document.mtime) }} · 哈希
          <span class="panel-mono">{{ document.hash.slice(0, 12) }}…</span>
        </p>

        <el-input
          v-model="content"
          type="textarea"
          :autosize="{ minRows: 18, maxRows: 30 }"
          class="editor panel-mono"
          spellcheck="false"
        />

        <el-alert
          v-if="lineErrors.length"
          type="error"
          show-icon
          :closable="false"
          title="存在无法解析的行，未保存"
          class="panel-page__alert"
        >
          <ul>
            <li v-for="item in lineErrors" :key="`${item.line}-${item.message}`">
              第 {{ item.line }} 行：{{ item.message }}
            </li>
          </ul>
        </el-alert>

        <div class="actionbar">
          <span class="panel-muted">{{ dirty ? "有未保存的修改" : "与服务端一致" }}</span>
          <div>
            <el-button :disabled="!dirty" @click="cancel">取消</el-button>
            <el-button type="primary" :disabled="!dirty" :loading="saving" @click="save">保存</el-button>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="备份" name="backups">
        <el-table v-if="backups.length" :data="backups" size="small">
          <el-table-column prop="name" label="备份文件" />
          <el-table-column label="时间" width="220">
            <template #default="{ row }">{{ formatTime(row.mtime) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button size="small" @click="restore(row.name)">恢复</el-button>
            </template>
          </el-table-column>
        </el-table>
        <EmptyState v-else title="尚无备份" description="保存地址库时会自动备份，最多保留 30 份" retry-label="" />
      </el-tab-pane>
    </el-tabs>
  </section>
</template>

<style scoped>
.editor :deep(textarea) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.6;
}

.panel-page__alert {
  margin-top: 12px;
}

.actionbar {
  position: sticky;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  margin-top: 16px;
  background: var(--panel-surface);
  border: 1px solid var(--panel-border);
  border-radius: 8px;
}

ul {
  margin: 6px 0 0;
  padding-left: 18px;
}
</style>
