<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";
import { onBeforeRouteLeave } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";

import { get, post, put } from "../api";
import EmptyState from "../components/EmptyState.vue";
import ErrorState from "../components/ErrorState.vue";
import PageHeader from "../components/PageHeader.vue";
import type { LibraryDocument } from "../types";
import { formatSize, formatTime } from "../utils/format";

interface BackupFile {
  name: string;
  size: number;
  mtime: string;
}

interface LineError {
  line: number;
  message: string;
}

const activeTab = ref("edit");
const document = ref<LibraryDocument | null>(null);
const content = ref("");
const serverContent = ref("");
const loadError = ref("");
const lineErrors = ref<LineError[]>([]);
const backups = ref<BackupFile[]>([]);
const loading = ref(false);
const saving = ref(false);

const editor = ref<HTMLTextAreaElement | null>(null);
const gutter = ref<HTMLElement | null>(null);

const dirty = computed(() => content.value !== serverContent.value);
const lineCount = computed(() => content.value.split("\n").length);
const lineNumbers = computed(() =>
  Array.from({ length: lineCount.value }, (_, index) => index + 1).join("\n"),
);

function applyDocument(data: LibraryDocument) {
  document.value = data;
  content.value = data.content;
  serverContent.value = data.content;
  lineErrors.value = [];
  void nextTick(() => {
    if (gutter.value && editor.value) gutter.value.scrollTop = editor.value.scrollTop;
  });
}

async function load() {
  loading.value = true;
  loadError.value = "";
  try {
    applyDocument(await get<LibraryDocument>("/api/library"));
  } catch (exception) {
    loadError.value = (exception as Error).message;
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

function syncScroll() {
  if (gutter.value && editor.value) gutter.value.scrollTop = editor.value.scrollTop;
}

function focusLine(line: number) {
  const element = editor.value;
  if (!element) return;
  const lines = content.value.split("\n");
  let offset = 0;
  for (let index = 0; index < Math.min(line - 1, lines.length); index += 1) {
    offset += lines[index].length + 1;
  }
  element.focus();
  element.setSelectionRange(offset, offset + (lines[line - 1]?.length ?? 0));
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
    applyDocument(
      await post<LibraryDocument>(`/api/library/backups/${encodeURIComponent(name)}/restore`),
    );
    ElMessage.success("已恢复备份");
    await loadBackups();
  } catch (exception) {
    ElMessage.error((exception as Error).message);
  }
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
  <section class="page page--flush">
    <PageHeader title="IP 库" subtitle="在线编辑候选地址库；保存前逐行校验并自动备份">
      <el-button :loading="loading" @click="load">重新加载</el-button>
    </PageHeader>

    <ErrorState v-if="loadError" :message="loadError" @retry="load" />

    <el-tabs v-model="activeTab">
      <el-tab-pane label="编辑" name="edit">
        <p v-if="document" class="muted stats">
          {{ document.line_count }} 行 · 网段 {{ document.stats.networks }} · 固定条目
          {{ document.stats.fixed }} · 跳过 {{ document.stats.skipped }} · 修改时间
          {{ formatTime(document.mtime) }} · hash
          <span class="mono">{{ document.hash.slice(0, 12) }}…</span>
        </p>

        <div class="editor">
          <pre ref="gutter" class="editor__gutter mono" aria-hidden="true">{{ lineNumbers }}</pre>
          <textarea
            ref="editor"
            v-model="content"
            class="editor__code mono"
            spellcheck="false"
            aria-label="候选地址库内容"
            @scroll="syncScroll"
          />
        </div>

        <div v-if="lineErrors.length" class="line-errors" role="alert">
          <strong>存在无法解析的行，未保存</strong>
          <ul>
            <li v-for="item in lineErrors" :key="`${item.line}-${item.message}`">
              <button type="button" class="line-link" @click="focusLine(item.line)">
                第 {{ item.line }} 行
              </button>
              ：{{ item.message }}
            </li>
          </ul>
        </div>

        <div class="actionbar">
          <span class="muted">{{ dirty ? "有未保存的修改" : "与服务端一致" }}</span>
          <div class="actionbar__buttons">
            <el-button :disabled="!dirty" @click="cancel">取消</el-button>
            <el-button type="primary" :disabled="!dirty" :loading="saving" @click="save">
              保存
            </el-button>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="备份" name="backups">
        <section v-if="backups.length" class="panel">
          <div class="panel__body">
        <el-table :data="backups" size="small">
          <el-table-column prop="name" label="备份文件" min-width="220">
            <template #default="{ row }"><span class="mono">{{ row.name }}</span></template>
          </el-table-column>
          <el-table-column label="时间" width="180">
            <template #default="{ row }">{{ formatTime(row.mtime) }}</template>
          </el-table-column>
          <el-table-column label="大小" width="100">
            <template #default="{ row }">{{ formatSize(row.size) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button size="small" @click="restore(row.name)">恢复</el-button>
            </template>
          </el-table-column>
        </el-table>
          </div>
        </section>
        <EmptyState
          v-else
          title="尚无备份"
          description="保存地址库时会自动备份，最多保留 30 份"
          action-label="刷新"
          @action="loadBackups"
        />
      </el-tab-pane>
    </el-tabs>
  </section>
</template>

<style scoped>
.stats {
  margin: 0 0 var(--space-3);
  font-size: 12px;
}

.editor {
  display: grid;
  grid-template-columns: 52px 1fr;
  height: 460px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--surface);
}

.editor__gutter {
  margin: 0;
  padding: var(--space-3) 8px;
  overflow: hidden;
  text-align: right;
  color: var(--text-muted);
  background: var(--surface-2);
  border-right: 1px solid var(--border);
  font-size: 12px;
  line-height: 20px;
  user-select: none;
}

.editor__code {
  width: 100%;
  height: 100%;
  padding: var(--space-3);
  border: 0;
  resize: none;
  background: transparent;
  color: var(--text);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 20px;
  white-space: pre;
  overflow: auto;
  outline: none;
}

.editor__code:focus-visible {
  outline: 2px solid var(--focus);
  outline-offset: -2px;
}

.line-errors {
  margin-top: var(--space-3);
  padding: var(--space-3);
  border: 1px solid color-mix(in srgb, var(--danger) 45%, var(--border));
  background: color-mix(in srgb, var(--danger) 8%, var(--surface));
  border-radius: var(--radius-md);
  font-size: 13px;
}

.line-errors ul {
  margin: 6px 0 0;
  padding-left: 18px;
}

.line-link {
  padding: 0;
  border: 0;
  background: none;
  color: var(--info);
  cursor: pointer;
  font: inherit;
  text-decoration: underline;
}

@media (max-width: 767px) {
  .editor {
    height: 360px;
    grid-template-columns: 44px 1fr;
  }
}
</style>
