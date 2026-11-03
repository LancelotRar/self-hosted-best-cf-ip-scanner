<script setup lang="ts">
import {
  Check,
  Clock,
  Close,
  Refresh,
  RefreshLeft,
  RefreshRight,
  VideoPlay,
} from "@element-plus/icons-vue";
import { onMounted, ref } from "vue";
import { onBeforeRouteLeave, useRoute } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";

import { post } from "../api";
import EmptyState from "../components/EmptyState.vue";
import ConfigLibraryTab from "../components/ConfigLibraryTab.vue";
import ConfigScheduleTab from "../components/ConfigScheduleTab.vue";
import ErrorState from "../components/ErrorState.vue";
import PageHeader from "../components/PageHeader.vue";
import ParamField from "../components/ParamField.vue";
import SaveResultPanel from "../components/SaveResultPanel.vue";
import UnsavedDialog from "../components/UnsavedDialog.vue";
import { useTableWidths } from "../composables/useTableWidths";
import { useConfigStore } from "../stores/config";
import type { Param } from "../types";
import { formatTime } from "../utils/format";

const store = useConfigStore();
const { widthFor: versionWidth, onHeaderDragEnd: onVersionDragEnd } = useTableWidths("config-versions");
const route = useRoute();
const activeTab = ref(route.query.tab === "schedule" ? "schedule" : "scanner");
const versionsVisible = ref(false);
const loadError = ref("");
const saveError = ref("");
const restarting = ref(false);
const unsavedVisible = ref(false);
const leaving = ref<((ok: boolean) => void) | null>(null);

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

async function saveAndLeave() {
  try {
    await store.save();
    ElMessage.success("已保存");
    resolveLeave(true);
  } catch (error) {
    ElMessage.error((error as Error).message);
    resolveLeave(false);
  }
}

function discardAndLeave() {
  store.cancel();
  resolveLeave(true);
}

const GROUPS: Record<string, string[]> = {
  scanner: ["探测端点", "探测参数", "采样", "输入输出", "运行身份"],
  publish: ["发布", "网络代理"],
  schedule: ["定时计划"],
  readonly: ["只读设置"],
};

const groupedFor = (tab: string): Array<{ name: string; params: Param[] }> =>
  (GROUPS[tab] ?? [])
    .map((name) => ({
      name,
      // 时区在「设置 · 常规」里维护，参数页不再重复出现
      params: store.params.filter((param) => param.group === name && param.name !== "TZ"),
    }))
    .filter((group) => group.params.length > 0);

function update(param: Param, value: unknown) {
  store.applyLocal({ [param.name]: value });
}

async function load() {
  loadError.value = "";
  try {
    await store.load();
  } catch (error) {
    loadError.value = (error as Error).message;
  }
}

async function save() {
  saveError.value = "";
  try {
    await store.save();
    ElMessage.success("已保存");
  } catch (error) {
    const failure = error as Error & { status?: number };
    if (failure.status === 409) {
      try {
        await ElMessageBox.confirm(
          "配置文件已被其他方式修改。重新加载会丢弃当前未保存的修改。",
          "文件已被修改",
          { confirmButtonText: "重新加载", cancelButtonText: "取消", type: "warning" },
        );
        await store.load();
      } catch {
        /* 用户取消 */
      }
      return;
    }
    saveError.value = failure.message;
  }
}

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

onMounted(load);

onBeforeRouteLeave(async () => {
  if (!store.dirty) return true;
  return askLeave();
});
</script>

<template>
  <section class="page page--flush">
    <PageHeader
      title="参数调整"
      subtitle="保存即改写 .env；扫描器下一轮读取，调度变更热重载"
    />

    <div class="config-toolbar">
      <span v-if="store.hash" class="muted file-meta">
        {{ formatTime(store.mtime) }} ·
        <span class="mono">sha256 {{ store.hash.slice(0, 12) }}…</span> ·
        {{ store.fileSize }} B
      </span>
      <span class="spacer" />
      <el-button text @click="openVersions"><el-icon><Clock /></el-icon>版本历史</el-button>
      <el-button text :loading="store.loading" @click="load">
        <el-icon><RefreshRight /></el-icon>重新加载
      </el-button>
    </div>

    <ErrorState v-if="loadError" :message="loadError" @retry="load" />
    <ErrorState v-else-if="saveError" title="保存失败" :message="saveError" action-label="关闭" @retry="saveError = ''" />

    <div
      v-if="store.lastError && store.lastError.details"
      class="field-errors"
      role="alert"
    >
      <strong>字段级错误</strong>
      <ul>
        <li
          v-for="(detail, index) in (store.lastError.details as Array<Record<string, unknown>>)"
          :key="index"
        >
          {{ detail.name ?? "配置" }}：{{ detail.message ?? detail }}
        </li>
      </ul>
    </div>

    <el-skeleton v-if="store.loading && !store.params.length" :rows="8" animated />

    <template v-else-if="store.params.length">
      <el-tabs v-model="activeTab" class="config-tabs">
        <el-tab-pane label="扫描参数" name="scanner" lazy>
          <div class="config-card">
          <el-collapse :model-value="groupedFor('scanner').map((group) => group.name)">
            <el-collapse-item
              v-for="group in groupedFor('scanner')"
              :key="group.name"
              :name="group.name"
              :title="group.name"
            >
              <div class="field-grid">
                <ParamField
                  v-for="param in group.params"
                  :key="param.name"
                  :param="param"
                  :model-value="store.values[param.name]"
                  @update:model-value="update(param, $event)"
                />
              </div>
            </el-collapse-item>
          </el-collapse>
          </div>
        </el-tab-pane>

        <el-tab-pane label="自定义 IP 库" name="library" lazy>
          <ConfigLibraryTab />
        </el-tab-pane>

        <el-tab-pane label="发布与代理" name="publish" lazy>
          <div class="config-card">
          <el-collapse :model-value="groupedFor('publish').map((group) => group.name)">
            <el-collapse-item
              v-for="group in groupedFor('publish')"
              :key="group.name"
              :name="group.name"
              :title="group.name"
            >
              <div class="field-grid">
                <ParamField
                  v-for="param in group.params"
                  :key="param.name"
                  :param="param"
                  :model-value="store.values[param.name]"
                  @update:model-value="update(param, $event)"
                />
              </div>
            </el-collapse-item>
          </el-collapse>
          </div>
        </el-tab-pane>

        <el-tab-pane label="定时计划" name="schedule" lazy>
          <ConfigScheduleTab />
        </el-tab-pane>

        <el-tab-pane label="只读设置" name="readonly" lazy>
          <div class="config-card">
          <p class="muted readonly-hint">
            只读参数需要手工修改 .env 并重建容器（docker compose up -d）。
          </p>
          <el-collapse :model-value="groupedFor('readonly').map((group) => group.name)">
            <el-collapse-item
              v-for="group in groupedFor('readonly')"
              :key="group.name"
              :name="group.name"
              :title="group.name"
            >
              <div class="field-grid">
                <ParamField
                  v-for="param in group.params"
                  :key="param.name"
                  :param="param"
                  :model-value="store.values[param.name]"
                  @update:model-value="update(param, $event)"
                />
              </div>
            </el-collapse-item>
          </el-collapse>
          </div>
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
        <span class="muted">
          {{ store.dirty ? `未保存 ${store.dirtyCount} 项` : "没有未保存的修改" }}
        </span>
        <div class="actionbar__buttons">
          <el-button :disabled="!store.dirty" @click="store.cancel()"><el-icon><Close /></el-icon>取消</el-button>
          <el-button type="primary" :disabled="!store.dirty" :loading="store.saving" @click="save">
            <el-icon><Check /></el-icon>
            保存
          </el-button>
        </div>
      </div>
    </template>

    <el-drawer v-model="versionsVisible" title="配置版本" size="60%">
      <el-table border v-if="store.versions.length" :data="store.versions" size="small" @header-dragend="onVersionDragEnd">
        <el-table-column prop="id" label="版本" :width="versionWidth('版本') ?? 70" />
        <el-table-column label="时间" :width="versionWidth('时间') ?? 180">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="actor" label="操作者" :width="versionWidth('操作者') ?? 90" />
        <el-table-column prop="diff" label="变更（已脱敏）" :width="versionWidth('变更（已脱敏）')" min-width="240">
          <template #default="{ row }">
            <span class="mono diff">{{ row.diff }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" :width="versionWidth('操作') ?? 90">
          <template #default="{ row }">
            <el-button size="small" @click="rollback(row.id)">回滚</el-button>
          </template>
        </el-table-column>
      </el-table>
      <EmptyState v-else title="尚无配置版本" description="每次成功保存都会生成一个可回滚版本" />
    </el-drawer>

    <UnsavedDialog
      v-model="unsavedVisible"
      :saving="store.saving"
      description="有未保存的参数修改，离开后这些修改会丢失。"
      @save="saveAndLeave"
      @discard="discardAndLeave"
    />
  </section>
</template>

<style scoped>
.config-toolbar {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  margin: -4px 0 6px;
}

.config-toolbar .file-meta {
  margin-right: 8px;
}

.file-meta {
  color: var(--text-faint);
  font-size: 12px;
}

.field-errors {
  margin-bottom: var(--space-3);
  padding: var(--space-3);
  border: 1px solid color-mix(in srgb, var(--danger) 45%, var(--border));
  background: color-mix(in srgb, var(--danger) 8%, var(--surface));
  border-radius: var(--radius-md);
  font-size: 13px;
}

.field-errors ul {
  margin: 6px 0 0;
  padding-left: 18px;
}

.config-tabs :deep(.el-tabs__content) {
  padding-top: var(--space-3);
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 40px;
}

.field-grid :deep(.field--wide) {
  grid-column: 1 / -1;
}

@media (max-width: 1199px) {
  .field-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

.config-card {
  padding: var(--space-5) var(--space-6);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}

@media (max-width: 767px) {
  .config-card {
    padding: var(--space-3);
  }
}

.readonly-hint {
  margin: 0 0 var(--space-3);
  font-size: 12px;
}

.diff {
  font-size: 11px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
