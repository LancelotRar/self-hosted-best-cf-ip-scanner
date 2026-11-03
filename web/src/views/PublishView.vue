<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { onBeforeRouteLeave } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";

import { get, put } from "../api";
import ParamField from "../components/ParamField.vue";
import EmptyState from "../components/EmptyState.vue";
import type { Param, RunRecord, SaveResult } from "../types";

const activeTab = ref("params");
const params = ref<Param[]>([]);
const hash = ref("");
const values = ref<Record<string, unknown>>({});
const serverValues = ref<Record<string, unknown>>({});
const last = ref<RunRecord | null>(null);
const error = ref("");
const saving = ref(false);
const result = ref<SaveResult | null>(null);

const dirtyParams = computed(() =>
  params.value.filter(
    (param) =>
      JSON.stringify(values.value[param.name]) !== JSON.stringify(serverValues.value[param.name]),
  ),
);
const dirty = computed(() => dirtyParams.value.length > 0);

async function load() {
  error.value = "";
  try {
    const data = await get<{
      hash: string;
      params: Param[];
      last: RunRecord | null;
    }>("/api/publish");
    params.value = data.params;
    hash.value = data.hash;
    last.value = data.last;
    const snapshot: Record<string, unknown> = {};
    for (const param of data.params) {
      snapshot[param.name] = param.value;
    }
    serverValues.value = { ...snapshot };
    values.value = { ...snapshot };
  } catch (exception) {
    error.value = (exception as Error).message;
  }
}

function update(param: Param, value: unknown) {
  values.value = { ...values.value, [param.name]: value };
}

function encode(param: Param, value: unknown): string {
  if (Array.isArray(value)) return value.join(",");
  if (param.kind === "bool") return value ? "true" : "false";
  return value === null || value === undefined ? "" : String(value);
}

async function save() {
  saving.value = true;
  try {
    const payload: Record<string, string> = {};
    for (const param of dirtyParams.value) {
      payload[param.name] = encode(param, values.value[param.name]);
    }
    result.value = await put<SaveResult>("/api/publish", { hash: hash.value, values: payload });
    ElMessage.success("已保存发布参数");
    await load();
  } catch (exception) {
    ElMessage.error((exception as Error).message);
  } finally {
    saving.value = false;
  }
}

function cancel() {
  values.value = { ...serverValues.value };
}

function exitLabel(code: number | null): string {
  if (code === null) return "—";
  return code === 0 ? "成功" : `失败（${code}）`;
}

function formatTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false });
}

onMounted(load);

onBeforeRouteLeave(async () => {
  if (!dirty.value) return true;
  try {
    await ElMessageBox.confirm("发布参数有未保存的修改，确定离开？", "未保存的修改", {
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
      <h1>发布</h1>
      <el-button @click="load">重新加载</el-button>
    </div>

    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false">
      <el-button size="small" @click="load">重试</el-button>
    </el-alert>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="参数" name="params">
        <ParamField
          v-for="param in params"
          :key="param.name"
          :param="param"
          :model-value="values[param.name]"
          @update:model-value="update(param, $event)"
        />
        <div class="actionbar">
          <span class="panel-muted">{{ dirty ? "有未保存的修改" : "与服务端一致" }}</span>
          <div>
            <el-button :disabled="!dirty" @click="cancel">取消</el-button>
            <el-button type="primary" :disabled="!dirty" :loading="saving" @click="save">保存</el-button>
          </div>
        </div>
        <el-alert
          v-if="result"
          type="success"
          :closable="false"
          show-icon
          :title="`已写入 ${result.changed.length} 项；核对状态：${result.verification.status}`"
          class="panel-page__alert"
        />
      </el-tab-pane>

      <el-tab-pane label="最近结果" name="last">
        <template v-if="last">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="轮次">{{ last.run_id }}</el-descriptions-item>
            <el-descriptions-item label="结束时间">{{ formatTime(last.finished_at) }}</el-descriptions-item>
            <el-descriptions-item label="扫描">{{ exitLabel(last.scan_exit) }}</el-descriptions-item>
            <el-descriptions-item label="发布">{{ exitLabel(last.publish_exit) }}</el-descriptions-item>
            <el-descriptions-item label="摘要" :span="2">{{ last.summary ?? "—" }}</el-descriptions-item>
          </el-descriptions>
        </template>
        <EmptyState v-else title="尚无发布记录" description="尚无发布记录（完成一轮扫描后生成）" retry-label="" />
      </el-tab-pane>
    </el-tabs>
  </section>
</template>

<style scoped>
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

.panel-page__alert {
  margin-top: 12px;
}
</style>
