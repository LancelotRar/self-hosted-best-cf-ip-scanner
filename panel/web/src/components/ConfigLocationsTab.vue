<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";
import { onBeforeRouteLeave } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { Check, Connection, Delete, InfoFilled, Plus, RefreshLeft, Search } from "@element-plus/icons-vue";

import { ApiError, get, put } from "../api";
import EmptyState from "./EmptyState.vue";
import ErrorState from "./ErrorState.vue";
import UnsavedDialog from "./UnsavedDialog.vue";
import type { LocationEntry, LocationsDocument } from "../types";

const CODE_RE = /^[A-Z]{3}$/;
const COUNTRY_RE = /^[A-Z]{2}$/;

const doc = ref<LocationsDocument | null>(null);
const rows = ref<LocationEntry[]>([]);
const query = ref("");
const loading = ref(true);
const saving = ref(false);
const loadError = ref("");
const saveError = ref("");
const fieldErrors = ref<string[]>([]);
const unsavedVisible = ref(false);
const leaving = ref<((ok: boolean) => void) | null>(null);

const snapshot = computed(() => JSON.stringify(doc.value?.entries ?? []));
const dirty = computed(
  () => Boolean(doc.value) && JSON.stringify(rows.value) !== snapshot.value,
);

/** 与后端同一套规则：三字母机房代码、两字母国家代码、代码不可重复。 */
const rowErrors = computed(() => {
  const result = new Map<number, string[]>();
  const seen = new Map<string, number>();
  rows.value.forEach((row, index) => {
    const messages: string[] = [];
    if (!CODE_RE.test(row.code)) messages.push("机房代码要 3 个大写字母");
    if (!COUNTRY_RE.test(row.country)) messages.push("国家代码要 2 个大写字母");
    if (CODE_RE.test(row.code)) {
      const first = seen.get(row.code);
      if (first === undefined) seen.set(row.code, index);
      else messages.push(`与第 ${first + 1} 行重复`);
    }
    if (messages.length) result.set(index, messages);
  });
  return result;
});

const invalid = computed(() => rowErrors.value.size > 0);

/** 400+ 行，必须能按代码或国家筛。索引保留原行号，错误定位才不会错位。 */
const filtered = computed(() => {
  const needle = query.value.trim().toUpperCase();
  return rows.value
    .map((row, index) => ({ row, index }))
    .filter(({ row }) =>
      needle ? row.code.includes(needle) || row.country.includes(needle) : true,
    );
});

function apply(data: LocationsDocument) {
  doc.value = data;
  rows.value = data.entries.map((entry) => ({ ...entry }));
}

async function load() {
  loading.value = true;
  loadError.value = "";
  try {
    apply(await get<LocationsDocument>("/api/locations"));
  } catch (error) {
    loadError.value = (error as Error).message;
  } finally {
    loading.value = false;
  }
}

function updateCell(index: number, field: keyof LocationEntry, value: string | number) {
  const text = String(value);
  rows.value[index][field] =
    field === "code" ? text.toUpperCase().replace(/\s/g, "") : text.toUpperCase().replace(/\s/g, "");
}

function addRow() {
  rows.value.push({ code: "", country: "" });
  query.value = "";
  void nextTick(() => {
    const inputs = document.querySelectorAll<HTMLInputElement>(".loc-row__code input");
    inputs[inputs.length - 1]?.focus();
  });
}

function removeRow(index: number) {
  rows.value.splice(index, 1);
}

function restore() {
  rows.value = (doc.value?.entries ?? []).map((entry) => ({ ...entry }));
  fieldErrors.value = [];
  saveError.value = "";
}

async function save() {
  if (!doc.value || invalid.value) return;
  saving.value = true;
  saveError.value = "";
  fieldErrors.value = [];
  try {
    apply(
      await put<LocationsDocument>("/api/locations", {
        hash: doc.value.hash,
        entries: rows.value,
      }),
    );
    ElMessage.success("机房映射已保存，下一轮扫描生效");
  } catch (error) {
    const failure = error as ApiError;
    if (failure.status === 409) {
      try {
        await ElMessageBox.confirm(
          "机房映射已被其他方式修改。重新加载会丢弃当前未保存的修改。",
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
      fieldErrors.value = (failure.details as Array<{ line?: number; message?: string }>).map(
        (detail) => `第 ${detail.line ?? "?"} 行：${detail.message ?? "格式不正确"}`,
      );
    }
    saveError.value = failure.message;
  } finally {
    saving.value = false;
  }
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

function discardAndLeave() {
  restore();
  resolveLeave(true);
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

  <section v-else class="block">
    <header class="block__head">
      <el-icon><Connection /></el-icon><span>机房映射</span>
    </header>
    <div class="panel block__card">
      <div class="loc-meta">
        <p class="muted loc-card__sub">
          机房代码 → 国家代码；决定订阅行末尾的国家与国旗标签（如
          <code class="mono">#SG 🇸🇬</code>）。
        </p>
        <span class="muted loc-card__count">共 {{ rows.length }} 条</span>
      </div>

      <p class="loc-note">
        <el-icon><InfoFilled /></el-icon>
        <span>
          内置映射已覆盖主流 Cloudflare 机房，<strong>非必要无需编辑</strong>。
          它只影响订阅列表里的国家/国旗标注，不影响扫描、排序与测速结果。
          留空或写错只会让该机房显示原始代码。
        </span>
      </p>

      <div class="loc-toolbar">
        <el-input v-model="query" clearable placeholder="搜索机房或国家代码" class="loc-search">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <span class="spacer" />
        <el-button @click="addRow"><el-icon><Plus /></el-icon>新增一行</el-button>
      </div>

      <ErrorState
        v-if="saveError && !fieldErrors.length"
        title="保存失败"
        :message="saveError"
        action-label="关闭"
        @retry="saveError = ''"
      />
      <ul v-if="fieldErrors.length" class="field-errors" role="alert">
        <li v-for="(message, index) in fieldErrors" :key="index">{{ message }}</li>
      </ul>

      <div class="loc-table" role="table" aria-label="机房映射">
        <div class="loc-table__head" role="row">
          <span role="columnheader">机房代码</span>
          <span role="columnheader">国家代码</span>
          <span role="columnheader" class="loc-table__action">操作</span>
        </div>

        <div class="loc-table__body">
          <div
            v-for="{ row, index } in filtered"
            :key="index"
            class="loc-row"
            :class="{ 'loc-row--invalid': rowErrors.has(index) }"
            :title="rowErrors.get(index)?.join('；')"
            role="row"
          >
            <el-input
              :model-value="row.code"
              class="loc-row__code mono"
              maxlength="3"
              placeholder="HKG"
              :aria-invalid="rowErrors.has(index)"
              @update:model-value="(value: string | number) => updateCell(index, 'code', value)"
            />
            <el-input
              :model-value="row.country"
              class="loc-row__country mono"
              maxlength="2"
              placeholder="HK"
              :aria-invalid="rowErrors.has(index)"
              @update:model-value="(value: string | number) => updateCell(index, 'country', value)"
            />
            <el-button
              text
              type="danger"
              class="loc-row__remove"
              :aria-label="`删除机房 ${row.code || '该行'}`"
              @click="removeRow(index)"
            >
              <el-icon><Delete /></el-icon>
            </el-button>
            <p v-if="rowErrors.has(index)" class="loc-row__error" role="alert">
              {{ rowErrors.get(index)?.join("；") }}
            </p>
          </div>

          <EmptyState
            v-if="!filtered.length"
            :title="rows.length ? '没有匹配的机房' : '映射为空'"
            :description="rows.length ? '换个关键词试试。' : '新增一行，或从内置默认值恢复。'"
          />
        </div>
      </div>

      <div class="loc-actions">
        <span class="muted">
          {{ invalid ? "有不合法的条目，修正后才能保存" : dirty ? "有未保存的修改" : "没有未保存的修改" }}
        </span>
        <span class="spacer" />
        <el-button :disabled="!dirty" @click="restore">
          <el-icon><RefreshLeft /></el-icon>还原
        </el-button>
        <el-button type="primary" :disabled="!dirty || invalid" :loading="saving" @click="save">
          <el-icon><Check /></el-icon>保存
        </el-button>
      </div>

      <UnsavedDialog
        v-model="unsavedVisible"
        description="机房映射有未保存的修改，离开后这些修改会丢失。"
        @discard="discardAndLeave"
        @stay="resolveLeave(false)"
      />
    </div>
  </section>
</template>

<style scoped>
.loc-meta,
.loc-note,
.loc-toolbar,
.loc-table,
.loc-actions {
  width: 100%;
  max-width: 900px;
  margin-left: auto;
  margin-right: auto;
}

.loc-meta {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
}

.loc-meta p {
  margin: 0;
}

.loc-card__sub {
  font-size: var(--fs-meta);
}

.loc-card__count {
  font-size: var(--fs-meta);
  white-space: nowrap;
}

.loc-note {
  display: flex;
  gap: 8px;
  margin: var(--space-3) 0 0;
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  color: var(--text-muted);
  font-size: 12.5px;
  line-height: 1.7;
}

.loc-note code {
  padding: 0 4px;
  border-radius: 4px;
  background: var(--surface);
}

.loc-toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-4);
}

.loc-search {
  max-width: 280px;
}

.loc-table {
  margin-top: var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  overflow: hidden;
}

.loc-table__head,
.loc-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) 40px;
  justify-content: start;
  gap: var(--space-3);
  align-items: center;
  padding: 6px var(--space-3);
}

.loc-table__head {
  font-size: var(--fs-meta);
  color: var(--text-muted);
  border-bottom: 1px solid var(--border);
}

.loc-table__action {
  text-align: right;
}

.loc-table__body {
  max-height: 420px;
  overflow-y: auto;
}

.loc-row {
  border-bottom: 1px dashed color-mix(in srgb, var(--border) 60%, transparent);
}

.loc-row:last-child {
  border-bottom: none;
}

.loc-row--invalid {
  background: color-mix(in srgb, var(--danger) 8%, transparent);
}

.loc-row__remove {
  justify-self: end;
}

.loc-row__error {
  grid-column: 1 / -1;
  margin: 0 0 2px;
  color: var(--danger);
  font-size: 12px;
  line-height: 1.5;
}

.loc-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-4);
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
