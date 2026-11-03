<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { onBeforeRouteLeave } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";

import { post } from "../api";
import ParamField from "../components/ParamField.vue";
import SaveResultPanel from "../components/SaveResultPanel.vue";
import { useConfigStore } from "../stores/config";
import type { Param } from "../types";

const store = useConfigStore();
const activeTab = ref("scanner");
const versionsVisible = ref(false);
const saveError = ref("");
const restarting = ref(false);

const GROUPS: Record<string, string[]> = {
  scanner: ["探测端点", "探测参数", "采样", "输入输出", "调度", "运行身份"],
  publish: ["发布", "网络代理"],
  readonly: ["只读设置"],
};

const groupedFor = (tab: string): Array<{ name: string; params: Param[] }> =>
  (GROUPS[tab] ?? [])
    .map((name) => ({
      name,
      params: store.params.filter((param) => param.group === name),
    }))
    .filter((group) => group.params.length > 0);

async function verifyNow() {
  try {
    await store.verify();
    ElMessage.success("已重新核对");
  } catch (error) {
    ElMessage.error((error as Error).message);
  }
}

async function runNow() {
  try {
    await post("/api/runs");
    ElMessage.success("已触发一轮，可在「运行」页查看输出");
  } catch (error) {
    ElMessage.error((error as Error).message);
  }
}

function update(param: Param, value: unknown) {
  store.applyLocal({ [param.name]: value });
}

async function save() {
  saveError.value = "";
  try {
    await store.save();
    ElMessage.success("已保存");
  } catch (error) {
    const failure = error as Error & { status?: number; details?: unknown };
    if (failure.status === 409) {
      try {
        await ElMessageBox.confirm(
          "配置文件已被其他方式修改。重新加载会丢弃当前未保存的修改。",
          "文件已被修改",
          { confirmButtonText: "重新加载", cancelButtonText: "取消", type: "warning" },
        );
        await store.load();
      } catch {
        /* 用户取消：保留本地编辑 */
      }
      return;
    }
    saveError.value = failure.message;
  }
}

async function restartScanner() {
  restarting.value = true;
  try {
    await post("/api/system/restart", undefined, { "X-Confirm": "restart" });
    ElMessage.success("已请求重启扫描容器");
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    restarting.value = false;
  }
}

async function openVersions() {
  versionsVisible.value = true;
  try {
    await store.loadVersions();
  } catch (error) {
    ElMessage.error((error as Error).message);
  }
}

async function rollback(versionId: number) {
  try {
    await ElMessageBox.confirm("回滚会用该版本覆盖当前参数（敏感令牌保留当前值）。", "确认回滚", {
      confirmButtonText: "回滚",
      cancelButtonText: "取消",
      type: "warning",
    });
  } catch {
    return;
  }
  try {
    await store.rollback(versionId);
    ElMessage.success("已回滚");
    versionsVisible.value = false;
  } catch (error) {
    ElMessage.error((error as Error).message);
  }
}

function formatTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false });
}

onMounted(() => {
  void store.load().catch((error: Error) => {
    saveError.value = error.message;
  });
});

onBeforeRouteLeave(async () => {
  if (!store.dirty) return true;
  try {
    await ElMessageBox.confirm("有未保存的修改，确定离开？", "未保存的修改", {
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
      <h1>参数</h1>
      <div>
        <span class="panel-muted file-meta" v-if="store.hash">
          {{ store.mtime ? formatTime(store.mtime) : "—" }} · sha256
          <span class="panel-mono">{{ store.hash.slice(0, 12) }}…</span> · {{ store.fileSize }} B
        </span>
        <el-button @click="openVersions">版本历史</el-button>
        <el-button :loading="store.loading" @click="store.load()">重新加载</el-button>
      </div>
    </div>

    <el-alert v-if="saveError" :title="saveError" type="error" show-icon :closable="false" />

    <el-alert
      v-if="store.lastError && store.lastError.details"
      type="error"
      :closable="false"
      show-icon
      title="字段级错误"
      class="panel-page__alert"
    >
      <ul>
        <li v-for="(detail, index) in (store.lastError.details as Array<Record<string, unknown>>)" :key="index">
          {{ detail.name ?? "配置" }}：{{ detail.message ?? detail }}
        </li>
      </ul>
    </el-alert>

    <el-skeleton v-if="store.loading && !store.params.length" :rows="8" animated />

    <template v-else>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="扫描参数" name="scanner" lazy>
          <el-collapse :model-value="groupedFor('scanner').map((group) => group.name)">
            <el-collapse-item v-for="group in groupedFor('scanner')" :key="group.name" :name="group.name" :title="group.name">
              <ParamField
                v-for="param in group.params"
                :key="param.name"
                :param="param"
                :model-value="store.values[param.name]"
                @update:model-value="update(param, $event)"
              />
            </el-collapse-item>
          </el-collapse>
        </el-tab-pane>

        <el-tab-pane label="发布与代理" name="publish" lazy>
          <el-collapse :model-value="groupedFor('publish').map((group) => group.name)">
            <el-collapse-item v-for="group in groupedFor('publish')" :key="group.name" :name="group.name" :title="group.name">
              <ParamField
                v-for="param in group.params"
                :key="param.name"
                :param="param"
                :model-value="store.values[param.name]"
                @update:model-value="update(param, $event)"
              />
            </el-collapse-item>
          </el-collapse>
        </el-tab-pane>

        <el-tab-pane label="只读设置" name="readonly" lazy>
          <el-alert
            type="info"
            :closable="false"
            show-icon
            title="只读参数需要手工修改 .env 并重建容器（docker compose up -d）。"
          />
          <el-collapse :model-value="groupedFor('readonly').map((group) => group.name)">
            <el-collapse-item v-for="group in groupedFor('readonly')" :key="group.name" :name="group.name" :title="group.name">
              <ParamField
                v-for="param in group.params"
                :key="param.name"
                :param="param"
                :model-value="store.values[param.name]"
                @update:model-value="update(param, $event)"
              />
            </el-collapse-item>
          </el-collapse>
        </el-tab-pane>
      </el-tabs>

      <SaveResultPanel
        :result="store.lastResult"
        @close="store.lastResult = null"
        @restart="restartScanner"
        @verify="verifyNow"
        @run="runNow"
      />

      <div class="actionbar">
        <span class="panel-muted">
          {{ store.dirty ? `未保存 ${store.dirtyCount} 项` : "没有未保存的修改" }}
        </span>
        <div class="actionbar__buttons">
          <el-button :disabled="!store.dirty" @click="store.cancel()">取消</el-button>
          <el-button type="primary" :disabled="!store.dirty" :loading="store.saving" @click="save">
            保存
          </el-button>
        </div>
      </div>
    </template>

    <el-drawer v-model="versionsVisible" title="配置版本" size="60%">
      <el-table :data="store.versions" size="small">
        <el-table-column prop="id" label="版本" width="80" />
        <el-table-column prop="created_at" label="时间" width="200" />
        <el-table-column prop="actor" label="操作者" width="100" />
        <el-table-column prop="diff" label="变更（已脱敏）" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button size="small" @click="rollback(row.id)">回滚</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!store.versions.length" description="尚无配置版本" />
    </el-drawer>
  </section>
</template>

<style scoped>
.panel-page__alert {
  margin-top: 12px;
}

.result {
  margin-top: 16px;
}

.result__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.result__table {
  margin-top: 12px;
}

.result__restart {
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

.actionbar__buttons {
  display: flex;
  gap: 8px;
}

ul {
  margin: 6px 0 0;
  padding-left: 18px;
}
</style>
