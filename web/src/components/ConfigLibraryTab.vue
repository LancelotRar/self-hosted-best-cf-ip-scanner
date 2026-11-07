<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";
import { onBeforeRouteLeave } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { Check, Connection, RefreshLeft, Star } from "@element-plus/icons-vue";

import { ApiError, get, put } from "../api";
import ErrorState from "./ErrorState.vue";
import UnsavedDialog from "./UnsavedDialog.vue";
import type { LibraryDocument } from "../types";
import { formatCount } from "../utils/format";

type FieldError = { field?: string; line?: number; raw?: string; message?: string };

const library = ref<LibraryDocument | null>(null);
const draft = ref("");
const pinnedDraft = ref("");
const loading = ref(true);
const savingLibrary = ref(false);
const savingPinned = ref(false);
const loadError = ref("");
const saveError = ref("");
const fieldErrors = ref<FieldError[]>([]);
const unsavedVisible = ref(false);
const leaving = ref<((ok: boolean) => void) | null>(null);

const libraryDirty = computed(
  () => Boolean(library.value) && draft.value !== library.value?.content,
);
const pinnedDirty = computed(
  () => Boolean(library.value) && pinnedDraft.value !== library.value?.pinned.content,
);
const dirty = computed(() => libraryDirty.value || pinnedDirty.value);

const libraryErrors = computed(() =>
  fieldErrors.value.filter((item) => item.field !== "pinned"),
);
const pinnedErrors = computed(() =>
  fieldErrors.value.filter((item) => item.field === "pinned"),
);

/** 固定保留是纯文本列表，条数可以就地数，不必等保存。 */
const pinnedCount = computed(
  () =>
    pinnedDraft.value
      .split("\n")
      .filter((line) => line.trim() && !line.trimStart().startsWith("#")).length,
);

async function load() {
  loading.value = true;
  loadError.value = "";
  try {
    const data = await get<LibraryDocument>("/api/library");
    library.value = data;
    draft.value = data.content;
    pinnedDraft.value = data.pinned.content;
  } catch (error) {
    loadError.value = (error as Error).message;
  } finally {
    loading.value = false;
  }
}

function restoreLibrary() {
  draft.value = library.value?.content ?? "";
  fieldErrors.value = fieldErrors.value.filter((item) => item.field === "pinned");
  saveError.value = "";
}

function restorePinned() {
  pinnedDraft.value = library.value?.pinned.content ?? "";
  fieldErrors.value = fieldErrors.value.filter((item) => item.field !== "pinned");
  saveError.value = "";
}

/** 离开前只给两个选择：继续编辑 / 放弃修改。 */
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

function focusEditor() {
  void nextTick(() => {
    document.querySelector<HTMLTextAreaElement>(".library-editor__input textarea")?.focus();
  });
}

function discardAndLeave() {
  draft.value = library.value?.content ?? "";
  pinnedDraft.value = library.value?.pinned.content ?? "";
  resolveLeave(true);
}

async function submit(
  body: Record<string, unknown>,
  loadingFlag: typeof savingLibrary,
  field: "library" | "pinned",
) {
  if (!library.value) return;
  loadingFlag.value = true;
  saveError.value = "";
  fieldErrors.value = fieldErrors.value.filter((item) =>
    field === "pinned" ? item.field !== "pinned" : item.field === "pinned",
  );
  try {
    const data = await put<LibraryDocument>("/api/library", body);
    library.value = data;
    if (field === "library") draft.value = data.content;
    else pinnedDraft.value = data.pinned.content;
    ElMessage.success(field === "library" ? "地址库已保存，下一轮扫描生效" : "固定保留已保存");
  } catch (error) {
    const failure = error as ApiError;
    if (failure.status === 409) {
      try {
        await ElMessageBox.confirm(
          "内容已被其他方式修改。重新加载会丢弃当前未保存的修改。",
          "内容已被修改",
          { confirmButtonText: "重新加载", cancelButtonText: "取消", type: "warning" },
        );
        await load();
      } catch {
        /* 用户取消 */
      }
      return;
    }
    if (failure.status === 422 && Array.isArray(failure.details)) {
      fieldErrors.value = [...fieldErrors.value, ...(failure.details as FieldError[])];
    }
    saveError.value = failure.message;
  } finally {
    loadingFlag.value = false;
  }
}

async function saveLibrary() {
  if (!library.value) return;
  await submit(
    { hash: library.value.hash, content: draft.value },
    savingLibrary,
    "library",
  );
}

async function savePinned() {
  if (!library.value) return;
  await submit(
    {
      hash: library.value.hash,
      pinned: pinnedDraft.value,
      pinned_hash: library.value.pinned.hash,
    },
    savingPinned,
    "pinned",
  );
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
    <ErrorState
      v-if="saveError"
      title="保存失败"
      :message="saveError"
      action-label="关闭"
      @retry="saveError = ''"
    />

    <section class="block">
      <header class="block__head">
        <el-icon><Connection /></el-icon><span>Cloudflare 官方段</span>
      </header>
      <div class="panel block__card">
        <p class="library-desc">默认扫描库，来源 Cloudflare 官方 IPv4 段
          <a href="https://www.cloudflare.com/ips-v4" target="_blank" rel="noreferrer">
            https://www.cloudflare.com/ips-v4
          </a>
        </p>
        <p class="library-desc">若要排除某个网段，可在行首直接加 <code>#</code> 并写明依据，不建议整行删除</p>
        <p class="library-desc">若要排除部分网段，手动另起新的一行，写入网段，并在行首加 <code>#</code></p>
        <p class="library-desc">
          参与种子采样逻辑，展开后按采样步长抽 1 个代表 IP 进行扫描。
        </p>
        <p class="library-desc">当前 IP 总量：{{ formatCount(library?.stats.total) }}</p>

        <el-input
          v-model="draft"
          type="textarea"
          :rows="14"
          class="library-editor__input mono"
          spellcheck="false"
          placeholder="每行一条：104.16.0.0/13 或 104.17.3.3"
        />

        <ul v-if="libraryErrors.length" class="field-errors" role="alert">
          <li v-for="(item, index) in libraryErrors" :key="index">
            <template v-if="item.line">第 {{ item.line }} 行：</template>
            {{ item.message ?? "无法解析的条目" }}
            <span v-if="item.raw" class="mono">（{{ item.raw }}）</span>
          </li>
        </ul>

        <footer class="library-actions">
          <span class="muted">{{ libraryDirty ? "有未保存的修改" : "没有未保存的修改" }}</span>
          <span class="spacer" />
          <el-button :disabled="!libraryDirty" @click="restoreLibrary">
            <el-icon><RefreshLeft /></el-icon>还原
          </el-button>
          <el-button
            type="primary"
            :disabled="!libraryDirty"
            :loading="savingLibrary"
            @click="saveLibrary"
          >
            <el-icon><Check /></el-icon>保存
          </el-button>
        </footer>
      </div>
    </section>

    <section class="block">
      <header class="block__head">
        <el-icon><Star /></el-icon><span>固定保留</span>
      </header>
      <div class="panel block__card">
        <p class="library-meta">共 {{ formatCount(pinnedCount) }} 条</p>

        <p class="library-desc">
          此来源为用户希望固定添加的优选 IP。不做探测、不做机房映射，产物单独生成。
          文件名在「扫描参数 · 输入输出 · 固定保留文件名」中修改。
        </p>
        <p class="library-desc">
          格式，<code>IP</code> 或 <code>IP:端口</code>，可跟 <code>#备注</code>，如
          <code>1.2.3.4:443#手动添加</code>；省略端口时按 443。
        </p>

        <el-input
          v-model="pinnedDraft"
          type="textarea"
          :rows="6"
          class="library-editor__input mono"
          spellcheck="false"
          placeholder="1.2.3.4:443#手动添加"
        />

        <ul v-if="pinnedErrors.length" class="field-errors" role="alert">
          <li v-for="(item, index) in pinnedErrors" :key="index">
            <template v-if="item.line">第 {{ item.line }} 行：</template>
            {{ item.message ?? "无法解析的条目" }}
            <span v-if="item.raw" class="mono">（{{ item.raw }}）</span>
          </li>
        </ul>

        <footer class="library-actions">
          <span class="muted">{{ pinnedDirty ? "有未保存的修改" : "没有未保存的修改" }}</span>
          <span class="spacer" />
          <el-button :disabled="!pinnedDirty" @click="restorePinned">
            <el-icon><RefreshLeft /></el-icon>还原
          </el-button>
          <el-button
            type="primary"
            :disabled="!pinnedDirty"
            :loading="savingPinned"
            @click="savePinned"
          >
            <el-icon><Check /></el-icon>保存
          </el-button>
        </footer>
      </div>
    </section>

    <UnsavedDialog
      v-model="unsavedVisible"
      description="IP 库有未保存的修改，离开后这些修改会丢失。"
      @discard="discardAndLeave"
      @stay="focusEditor"
    />
  </template>
</template>

<style scoped>
.block + .block {
  margin-top: var(--space-5);
}

.library-meta {
  margin: 0 0 var(--space-2);
  font-size: 12px;
  color: var(--text-muted);
}

.library-desc {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.75;
  color: var(--text-muted);
}

.library-desc + .library-desc {
  margin-top: 4px;
}

.library-desc code {
  padding: 0 4px;
  border-radius: 4px;
  background: var(--surface-2);
  font-family: var(--font-mono);
}

.library-desc a {
  color: var(--text);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.library-editor__input {
  margin-top: var(--space-3);
}

.library-editor__input :deep(.el-textarea__inner) {
  font-family: var(--font-mono);
  font-size: 12.5px;
  line-height: 1.7;
  background: var(--surface-2);
  min-height: 120px;
}

.library-actions {
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
