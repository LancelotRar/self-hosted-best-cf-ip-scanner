<script setup lang="ts">
import {
  Aim, Check, Clock, Close, Connection, EditPen,
  RefreshRight, SetUp, Setting, Share, Upload,
} from "@element-plus/icons-vue";
import { computed, nextTick, onMounted, ref, type Component } from "vue";
import { onBeforeRouteLeave, useRoute } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";

import { post } from "../api";
import EmptyState from "../components/EmptyState.vue";
import ArtifactNamesEditor from "../components/ArtifactNamesEditor.vue";
import ConfigLibraryTab from "../components/ConfigLibraryTab.vue";
import ConfigLocationsTab from "../components/ConfigLocationsTab.vue";
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

/** 回到表单时把焦点放到第一个未保存的字段上，避免用户再找一遍。 */
function focusFirstDirty() {
  const name = store.changedParams[0]?.name;
  if (!name) return;
  void nextTick(() => {
    const element = document.getElementById(`param-${name}`);
    element?.focus();
    element?.scrollIntoView({ block: "center", behavior: "smooth" });
  });
}

function discardAndLeave() {
  store.cancel();
  resolveLeave(true);
}

const GROUPS: Record<string, string[]> = {
  scanner: ["探测端点", "探测参数", "采样"],
};

const groupedFor = (tab: string): Array<{ name: string; params: Param[] }> =>
  (GROUPS[tab] ?? [])
    .map((name) => ({
      name,
      // 时区在「设置 · 常规」里维护；底层参数由后端标记为 hidden，不进入面板
      params: store.params.filter(
        (param) => param.group === name && !param.hidden && param.name !== "TZ",
      ),
    }))
    .filter((group) => group.params.length > 0);

/** 两列卡片：偶数索引进左列、奇数索引进右列，各列独立堆叠，高度互不影响。 */
const scannerColumns = computed(() => {
  const groups = groupedFor("scanner");
  return [groups.filter((_, index) => index % 2 === 0), groups.filter((_, index) => index % 2 === 1)];
});

/** 产物与发布里的分组参数，供自定义卡片直接渲染。 */
const paramsFor = (group: string): Param[] =>
  store.params.filter((param) => param.group === group && !param.hidden);

/** 每个参数组一张卡片，标题在卡片外；图标按组名固定映射。 */
const GROUP_ICONS: Record<string, Component> = {
  探测端点: Connection,
  探测参数: SetUp,
  采样: Aim,
};

const iconFor = (name: string) => GROUP_ICONS[name] ?? Setting;

function update(param: Param, value: unknown) {
  store.applyLocal({ [param.name]: value });
}

/** 字段级错误用中文标签展示，避免把内部参数名抛给用户。 */
function labelFor(name: unknown): string {
  if (typeof name !== "string" || !name) return "配置";
  return store.params.find((param) => param.name === name)?.label ?? name;
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
          "设置已被其他方式修改。重新加载会丢弃当前未保存的修改。",
          "设置已被修改",
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
    <PageHeader title="参数调整" />

    <div v-if="activeTab !== 'schedule'" class="config-toolbar">
      <span class="config-toolbar__hint muted">修改后保存生效</span>
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
          {{ labelFor(detail.name) }}：{{ detail.message ?? detail }}
        </li>
      </ul>
    </div>

    <el-skeleton v-if="store.loading && !store.params.length" :rows="8" animated />

    <template v-else-if="store.params.length">
      <el-tabs v-model="activeTab" class="config-tabs">
        <el-tab-pane label="扫描参数" name="scanner" lazy>
          <div class="card-columns">
            <div
              v-for="(column, columnIndex) in scannerColumns"
              :key="columnIndex"
              class="card-column"
            >
              <section
                v-for="group in column"
                :key="group.name"
                class="block"
              >
                <header class="block__head">
                  <el-icon><component :is="iconFor(group.name)" /></el-icon>
                  <span>{{ group.name }}</span>
                </header>
                <div class="panel block__card">
                  <div class="field-grid">
                    <ParamField
                      v-for="param in group.params"
                      :key="param.name"
                      :param="param"
                      :model-value="store.values[param.name]"
                      @update:model-value="update(param, $event)"
                    />
                  </div>
                </div>
              </section>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="计划任务" name="schedule" lazy>
          <ConfigScheduleTab />
        </el-tab-pane>

        <el-tab-pane label="自定义 IP 库" name="library" lazy>
          <ConfigLibraryTab />
        </el-tab-pane>

        <el-tab-pane label="机房映射" name="locations" lazy>
          <ConfigLocationsTab />
        </el-tab-pane>

        <el-tab-pane label="产物定制" name="artifacts" lazy>
          <div class="card-columns">
            <section class="block">
              <header class="block__head">
                <el-icon><EditPen /></el-icon><span>文件名调整</span>
              </header>
              <div class="panel block__card">
                <ArtifactNamesEditor />
              </div>
            </section>

            <section class="block">
              <header class="block__head">
                <el-icon><SetUp /></el-icon><span>列表档位</span>
              </header>
              <div class="panel block__card">
                <div class="field-grid">
                  <ParamField
                    v-for="param in paramsFor('订阅列表')"
                    :key="param.name"
                    :param="param"
                    :model-value="store.values[param.name]"
                    @update:model-value="update(param, $event)"
                  />
                </div>
              </div>
            </section>
          </div>
        </el-tab-pane>

        <el-tab-pane label="推送设置" name="publish" lazy>
          <section class="block">
            <header class="block__head">
              <el-icon><Upload /></el-icon><span>推送设置</span>
            </header>
            <div class="panel block__card">
              <div class="field-grid field-grid--two">
                <ParamField
                  v-for="param in paramsFor('发布')"
                  :key="param.name"
                  :param="param"
                  :model-value="store.values[param.name]"
                  @update:model-value="update(param, $event)"
                />
              </div>
            </div>
          </section>
        </el-tab-pane>

        <el-tab-pane label="代理设置" name="proxy" lazy>
          <section class="block">
            <header class="block__head">
              <el-icon><Share /></el-icon><span>代理设置</span>
            </header>
            <div class="panel block__card">
              <div class="field-grid field-grid--two">
                <ParamField
                  v-for="param in paramsFor('网络代理')"
                  :key="param.name"
                  :param="param"
                  :model-value="store.values[param.name]"
                  @update:model-value="update(param, $event)"
                />
              </div>
            </div>
          </section>
        </el-tab-pane>
      </el-tabs>

      <SaveResultPanel
        v-if="activeTab !== 'schedule'"
        :result="store.lastResult"
        @close="store.lastResult = null"
        @restart="restartScanner"
        @verify="verifyNow"
        @run="runNow"
      />

      <div
        v-if="!['library', 'locations', 'schedule'].includes(activeTab)"
        class="actionbar"
      >
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
      description="有未保存的参数修改，离开后这些修改会丢失。"
      @discard="discardAndLeave"
      @stay="focusFirstDirty"
    />
  </section>
</template>

<style scoped>
.config-toolbar {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  margin: -4px 0 10px;
}

.config-toolbar__hint {
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
  padding-top: var(--space-4);
}

/* 双列卡片：两列各自堆叠，卡片高度只由自身内容决定 */
.card-columns {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-5);
  align-items: start;
}

.card-column {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  min-width: 0;
}

@media (max-width: 1199px) {
  .card-columns {
    grid-template-columns: minmax(0, 1fr);
  }
}

.field-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  row-gap: 24px;
}

.field-grid--two {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 32px;
}

.field-grid :deep(.field--wide) {
  grid-column: 1 / -1;
}

@media (max-width: 1199px) {
  .field-grid--two {
    grid-template-columns: minmax(0, 1fr);
  }
}

.diff {
  font-size: 11px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
