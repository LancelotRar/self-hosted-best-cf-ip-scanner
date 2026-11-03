<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";
import { onBeforeRouteLeave } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { Check, Document, RefreshLeft } from "@element-plus/icons-vue";

import { ApiError, get, put } from "../api";
import ErrorState from "./ErrorState.vue";
import UnsavedDialog from "./UnsavedDialog.vue";
import type { LibraryDocument } from "../types";
import { formatTime } from "../utils/format";

const library = ref<LibraryDocument | null>(null);
const draft = ref("");
const loading = ref(true);
const saving = ref(false);
const loadError = ref("");
const saveError = ref("");
const fieldErrors = ref<Array<{ line?: number; raw?: string; message?: string }>>([]);
const unsavedVisible = ref(false);
const leaving = ref<((ok: boolean) => void) | null>(null);

const dirty = computed(() => Boolean(library.value) && draft.value !== library.value?.content);

/** 文件开头的 `#` 注释块即是这份地址库的说明，移到面板里当作介绍展示。 */
const intro = computed(() => {
  const lines = (library.value?.content ?? "").split("\n");
  const block: string[] = [];
  for (const line of lines) {
    const text = line.trimEnd();
    if (!block.length && !text.trim()) continue;
    if (!text.startsWith("#")) break;
    block.push(text.replace(/^#\s?/, ""));
  }
  return block.join("\n").trim();
});

const entryCount = computed(
  () => draft.value.split("\n").filter((line) => line.trim() && !line.trimStart().startsWith("#")).length,
);

async function load() {
  loading.value = true;
  loadError.value = "";
  try {
    const data = await get<LibraryDocument>("/api/library");
    library.value = data;
    draft.value = data.content;
  } catch (error) {
    loadError.value = (error as Error).message;
  } finally {
    loading.value = false;
  }
}

function restore() {
  draft.value = library.value?.content ?? "";
  fieldErrors.value = [];
  saveError.value = "";
}

/** 离开前弹三选一：继续编辑 / 放弃修改 / 保存并离开。 */
function askLeave(): Promise<boolean> {
  unsavedVisible.value = true;
  return new Promise((resolve) => {
    leaving.value = resolve;
  });
}

function resolveLeave(ok: boolean) {
  unsavedVisible.value = false;
  leaving.value?.(ok);
  leaving.value = null;
}

/** 回到编辑时聚焦地址库输入框。 */
function focusEditor() {
  void nextTick(() => {
    document.querySelector<HTMLTextAreaElement>(".library-editor__input textarea")?.focus();
  });
}

function discardAndLeave() {
  restore();
  resolveLeave(true);
}

async function save() {
  if (!library.value) return;
  saving.value = true;
  saveError.value = "";
  fieldErrors.value = [];
  try {
    const data = await put<LibraryDocument>("/api/library", {
      hash: library.value.hash,
      content: draft.value,
    });
    library.value = data;
    draft.value = data.content;
    ElMessage.success("IP 库已保存，下一轮扫描生效");
  } catch (error) {
    const failure = error as ApiError;
    if (failure.status === 409) {
      try {
        await ElMessageBox.confirm(
          "地址库已被其他方式修改。重新加载会丢弃当前未保存的修改。",
          "文件已被修改",
          { confirmButtonText: "重新加载", cancelButtonText: "取消", type: "warning" },
        );
        await load();
      } catch {
        /* 用户取消 */
      }
      return;
    }
    if (failure.status === 422 && Array.isArray(failure.details)) {
      fieldErrors.value = failure.details as Array<{ line?: number; raw?: string; message?: string }>;
      saveError.value = failure.message;
      return;
    }
    saveError.value = failure.message;
  } finally {
    saving.value = false;
  }
}

onMounted(load);

onBeforeRouteLeave(async () => {
  if (!dirty.value) return true;
  return askLeave();
});
</script>

<template>
  <ErrorState v-if="loadError" :message="loadError" @retry="load" />
  <el-skeleton v-else-if="loading" :rows="6" animated />

  <template v-else>
    <div class="library-card">
      <section class="library-intro">
        <h3 class="library-intro__title"><el-icon><Document /></el-icon>格式说明</h3>
        <p v-if="intro" class="library-intro__text mono">{{ intro }}</p>
        <p v-else class="muted">
          每行一条：网段（如 104.16.0.0/24）、单个 IP 或 ip:port 固定条目；以 # 开头的行是注释。
        </p>
      </section>

      <section class="library-editor">
        <div class="library-editor__head">
          <h3 class="library-intro__title">地址条目</h3>
          <span class="muted library-editor__meta">
            {{ library?.line_count ?? 0 }} 行 · 条目 {{ entryCount }} · 网段
            {{ library?.stats.networks ?? 0 }} · 固定
            {{ library?.stats.fixed ?? 0 }} · 跳过 {{ library?.stats.skipped ?? 0 }}
            <template v-if="library?.mtime"> · 修改时间 {{ formatTime(library.mtime) }}</template>
          </span>
        </div>

        <p class="muted library-editor__hint">
          保存会覆盖数据目录下的地址库文件，并自动保留最近 30 份备份；下一轮扫描读取新内容。
        </p>

        <ErrorState
          v-if="saveError && !fieldErrors.length"
          title="保存失败"
          :message="saveError"
          action-label="关闭"
          @retry="saveError = ''"
        />
        <ul v-if="fieldErrors.length" class="field-errors" role="alert">
          <li v-for="(item, index) in fieldErrors" :key="index">
            <template v-if="item.line">第 {{ item.line }} 行：</template>
            {{ item.message ?? "无法解析的条目" }}
            <span v-if="item.raw" class="mono">（{{ item.raw }}）</span>
          </li>
        </ul>

        <el-input
          v-model="draft"
          type="textarea"
          :rows="16"
          class="library-editor__input mono"
          spellcheck="false"
          placeholder="每行一条：104.16.0.0/24 或 104.18.4.4:8443"
        />

        <div class="library-editor__actions">
          <span class="muted">{{ dirty ? "有未保存的修改" : "没有未保存的修改" }}</span>
          <span class="spacer" />
          <el-button :disabled="!dirty" @click="restore">
            <el-icon><RefreshLeft /></el-icon>还原
          </el-button>
          <el-button type="primary" :disabled="!dirty" :loading="saving" @click="save">
            <el-icon><Check /></el-icon>保存
          </el-button>
        </div>
      </section>
    </div>

    <UnsavedDialog
      v-model="unsavedVisible"
      description="IP 库有未保存的修改，离开后这些修改会丢失。"
      @discard="discardAndLeave"
      @stay="focusEditor"
    />
  </template>
</template>

<style scoped>
.library-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.library-intro,
.library-editor {
  padding: var(--space-4) var(--space-5);
}

.library-intro {
  border-bottom: 1px dashed var(--border);
}

.library-intro__title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text);
}

.library-intro__text {
  margin: var(--space-3) 0 0;
  padding: var(--space-4);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  color: var(--text-muted);
  font-size: 12.5px;
  line-height: 1.75;
  white-space: pre-wrap;
  overflow-x: auto;
}

.library-editor__head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-2) var(--space-4);
}

.library-editor__meta {
  font-size: 12px;
}

.library-editor__hint {
  margin: var(--space-2) 0 0;
  font-size: 12px;
}

.library-editor__input {
  margin-top: var(--space-3);
}

.library-editor__input :deep(.el-textarea__inner) {
  font-family: var(--font-mono);
  font-size: 12.5px;
  line-height: 1.7;
  background: var(--surface-2);
  min-height: 260px;
}

.library-editor__actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.field-errors {
  margin: var(--space-3) 0 0;
  padding: var(--space-3) var(--space-4);
  border: 1px solid color-mix(in srgb, var(--danger) 45%, var(--border));
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--danger) 8%, var(--surface));
  color: var(--text);
  font-size: 12.5px;
  line-height: 1.7;
  list-style: none;
}
</style>
