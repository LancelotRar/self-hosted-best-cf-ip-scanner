<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { onBeforeRouteLeave } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";

import { get, put } from "../api";
import EmptyState from "../components/EmptyState.vue";
import ErrorState from "../components/ErrorState.vue";
import PageHeader from "../components/PageHeader.vue";
import ParamField from "../components/ParamField.vue";
import SaveResultPanel from "../components/SaveResultPanel.vue";
import StatusPill from "../components/StatusPill.vue";
import type { Param, RunRecord, SaveResult } from "../types";
import { exitLabel, formatTime } from "../utils/format";

const activeTab = ref("params");
const params = ref<Param[]>([]);
const hash = ref("");
const values = ref<Record<string, unknown>>({});
const serverValues = ref<Record<string, unknown>>({});
const last = ref<RunRecord | null>(null);
const error = ref("");
const saving = ref(false);
const result = ref<SaveResult | null>(null);

const pushEnabled = computed(
  () => params.value.find((param) => param.name === "GIT_PUSH_ENABLED")?.value === true,
);

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
    const data = await get<{ hash: string; params: Param[]; last: RunRecord | null }>(
      "/api/publish",
    );
    params.value = data.params;
    hash.value = data.hash;
    last.value = data.last;
    const snapshot: Record<string, unknown> = {};
    for (const param of data.params) snapshot[param.name] = param.value;
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
    result.value = null;
    ElMessage.error((exception as Error).message);
  } finally {
    saving.value = false;
  }
}

function cancel() {
  values.value = { ...serverValues.value };
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
  <section class="page page--flush">
    <PageHeader title="发布" subtitle="Git 推送参数与最近一次推送结果">
      <StatusPill
        :tone="pushEnabled ? 'success' : 'neutral'"
        :label="pushEnabled ? '推送已开启' : '推送已关闭'"
      />
      <el-button @click="load">重新加载</el-button>
    </PageHeader>

    <ErrorState v-if="error" :message="error" @retry="load" />

    <el-tabs v-model="activeTab">
      <el-tab-pane label="参数" name="params">
        <div class="params">
          <ParamField
            v-for="param in params"
            :key="param.name"
            :param="param"
            :model-value="values[param.name]"
            @update:model-value="update(param, $event)"
          />
        </div>

        <SaveResultPanel :result="result" @close="result = null" />

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

      <el-tab-pane label="最近结果" name="last">
        <section v-if="last" class="panel">
          <header class="panel__head">最近一轮</header>
          <div class="panel__body">
            <dl class="kv">
              <dt>轮次</dt>
              <dd class="mono">{{ last.run_id }}</dd>
              <dt>结束时间</dt>
              <dd>{{ formatTime(last.finished_at) }}</dd>
              <dt>扫描</dt>
              <dd>{{ exitLabel(last.scan_exit) }}</dd>
              <dt>发布</dt>
              <dd>{{ exitLabel(last.publish_exit) }}</dd>
              <dt>摘要</dt>
              <dd>{{ last.summary ?? "—" }}</dd>
            </dl>
          </div>
        </section>
        <EmptyState
          v-else
          title="尚无发布记录"
          description="尚无发布记录（完成一轮扫描后生成）"
          action-label="刷新"
          @action="load"
        />
      </el-tab-pane>
    </el-tabs>
  </section>
</template>

<style scoped>
.params {
  padding: var(--space-2) var(--space-4);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}

.kv {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 8px 16px;
  margin: 0;
}

.kv dt {
  color: var(--text-muted);
  font-size: 12px;
}

.kv dd {
  margin: 0;
  overflow-wrap: anywhere;
}
</style>
