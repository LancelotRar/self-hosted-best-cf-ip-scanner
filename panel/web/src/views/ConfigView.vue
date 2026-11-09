<script setup lang="ts">
import {
  Aim, Check, Clock, Close, Connection, EditPen, Files,
  RefreshRight, SetUp, Share, Upload,
} from "@element-plus/icons-vue";
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { onBeforeRouteLeave, useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";

import { post } from "../api";
import EmptyState from "../components/EmptyState.vue";
import ArtifactNamesEditor from "../components/ArtifactNamesEditor.vue";
import PushListsEditor from "../components/PushListsEditor.vue";
import ConfigLibraryTab from "../components/ConfigLibraryTab.vue";
import ConfigLocationsTab from "../components/ConfigLocationsTab.vue";
import ConfigScheduleTab from "../components/ConfigScheduleTab.vue";
import HintIcon from "../components/HintIcon.vue";
import ErrorState from "../components/ErrorState.vue";
import PageHeader from "../components/PageHeader.vue";
import ParamField from "../components/ParamField.vue";
import SaveResultPanel from "../components/SaveResultPanel.vue";
import UnsavedDialog from "../components/UnsavedDialog.vue";
import { useTableWidths } from "../composables/useTableWidths";
import { useConfigStore } from "../stores/config";
import type { Param } from "../types";
import { effectLabel, formatTime } from "../utils/format";

const store = useConfigStore();
const { widthFor: versionWidth, onHeaderDragEnd: onVersionDragEnd } = useTableWidths("config-versions");
const route = useRoute();
const router = useRouter();
const CONFIG_TABS = [
  "scanner",
  "schedule",
  "library",
  "locations",
  "artifacts",
  "publish",
  "proxy",
] as const;
type ConfigTab = (typeof CONFIG_TABS)[number];

const activeTab = ref<ConfigTab>(
  CONFIG_TABS.includes(String(route.query.tab) as ConfigTab)
    ? (String(route.query.tab) as ConfigTab)
    : "scanner",
);
const versionsVisible = ref(false);
const diffVisible = ref(false);
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

/** 探测卡：目标 + TCP 握手阶段，按 schema 顺序逐行排列。 */
const PROBE_NAMES = [
  "PROBE_HOST",
  "PROBE_PORTS",
  "PROBE_CONCURRENCY",
  "TCP_ATTEMPTS",
  "TCP_MIN_SUCCESS",
  "TCP_TIMEOUT",
];

const paramsNamed = (names: string[]): Param[] =>
  names.flatMap((name) => {
    const param = store.params.find((item) => item.name === name);
    return param && !param.hidden ? [param] : [];
  });

const probeParams = computed(() => paramsNamed(PROBE_NAMES));

/** 校验与采样卡：端点校验 + 采样，和探测卡分成两张等宽卡片。 */
const checkSampleParams = computed(() =>
  store.params.filter(
    (param) => !param.hidden && (param.group === "探测参数" || param.group === "采样"),
  ).filter((param) => !PROBE_NAMES.includes(param.name)),
);

/** 产物与发布里的分组参数，供自定义卡片直接渲染。 */
const paramsFor = (group: string): Param[] =>
  store.params.filter((param) => param.group === group && !param.hidden);

/** 订阅列表：总开关/档位与各国条数分开展示，避免同一句说明重复六次。 */
const listSwitches = computed(() =>
  paramsFor("订阅列表").filter((param) => !param.name.startsWith("TOP_")),
);
const countryTops = computed(() =>
  paramsFor("订阅列表").filter((param) => param.name.startsWith("TOP_")),
);

function update(param: Param, value: unknown) {
  store.applyLocal({ [param.name]: value });
}

/** 把后端 details 映射到具体字段，错误直接出现在控件下方。 */
const fieldErrors = computed<Record<string, string>>(() => {
  const details = store.lastError?.details;
  if (!Array.isArray(details)) return {};
  const map: Record<string, string> = {};
  for (const detail of details) {
    if (!detail || typeof detail !== "object") continue;
    const item = detail as Record<string, unknown>;
    const name = typeof item.name === "string" ? item.name : "";
    if (!name || map[name]) continue;
    map[name] = typeof item.message === "string" ? item.message : "值不合法";
  }
  return map;
});

/** 没有字段归属的错误（例如 check-config 的整段输出）才进顶部汇总。 */
const generalErrors = computed<string[]>(() => {
  const details = store.lastError?.details;
  if (!Array.isArray(details)) return [];
  return details
    .map((detail) =>
      detail && typeof detail === "object"
        ? (detail as Record<string, unknown>)
        : null,
    )
    .filter((item): item is Record<string, unknown> => Boolean(item))
    .filter((item) => !item.name)
    .map((item) => (typeof item.message === "string" ? item.message : "配置校验失败"));
});

const hasFieldIssues = computed(
  () => Object.keys(fieldErrors.value).length > 0 || generalErrors.value.length > 0,
);

function valueText(value: unknown): string {
  if (Array.isArray(value)) return value.length ? value.join(", ") : "空";
  if (value === null || value === undefined || value === "") return "空";
  if (typeof value === "boolean") return value ? "开启" : "关闭";
  return String(value);
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

watch(
  () => route.query.tab,
  (value) => {
    const tab = String(value ?? "");
    if (CONFIG_TABS.includes(tab as ConfigTab) && tab !== activeTab.value) {
      activeTab.value = tab as ConfigTab;
    }
  },
);

watch(activeTab, (tab) => {
  if (route.query.tab === tab) return;
  void router.replace({ query: { ...route.query, tab } });
});

onBeforeRouteLeave(async () => {
  if (!store.dirty) return true;
  return askLeave();
});
</script>

<template>
  <section class="page page--flush">
    <PageHeader title="参数调整" subtitle="扫描、计划、IP 库与发布设置；修改后保存生效">
      <template #actions>
        <template v-if="!['schedule', 'library', 'locations'].includes(activeTab)">
          <el-button text @click="openVersions"><el-icon><Clock /></el-icon>版本历史</el-button>
          <el-button text :loading="store.loading" @click="load">
            <el-icon><RefreshRight /></el-icon>重新加载
          </el-button>
        </template>
      </template>
    </PageHeader>

    <ErrorState v-if="loadError" :message="loadError" @retry="load" />
    <ErrorState
      v-else-if="saveError && !hasFieldIssues"
      title="保存失败"
      :message="saveError"
      action-label="关闭"
      @retry="saveError = ''"
    />

    <div v-if="generalErrors.length" class="field-errors" role="alert">
      <strong>配置校验失败</strong>
      <ul>
        <li v-for="(message, index) in generalErrors" :key="index">{{ message }}</li>
      </ul>
    </div>

    <el-skeleton v-if="store.loading && !store.params.length" :rows="8" animated />

    <template v-else-if="store.params.length">
      <el-tabs v-model="activeTab" class="config-tabs">
        <el-tab-pane label="扫描参数" name="scanner" lazy>
          <div class="scanner-grid">
            <section class="block">
              <header class="block__head">
                <el-icon><Connection /></el-icon><span>探测</span>
                <span class="block__meta">保存后下一轮扫描生效</span>
              </header>
              <div class="panel block__card">
                <div class="scanner-list">
                  <ParamField
                    v-for="param in probeParams"
                    :key="param.name"
                    :param="param"
                    :error="fieldErrors[param.name]"
                    :model-value="store.values[param.name]"
                    @update:model-value="update(param, $event)"
                  />
                </div>
              </div>
            </section>

            <section class="block">
              <header class="block__head">
                <el-icon><Aim /></el-icon><span>校验与采样</span>
              </header>
              <div class="panel block__card">
                <div class="scanner-list">
                  <ParamField
                    v-for="param in checkSampleParams"
                    :key="param.name"
                    :param="param"
                    :error="fieldErrors[param.name]"
                    :model-value="store.values[param.name]"
                    @update:model-value="update(param, $event)"
                  />
                </div>
              </div>
            </section>
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
          <div class="config-pair">
            <section class="block">
              <header class="block__head">
                <el-icon><SetUp /></el-icon><span>列表档位</span>
              </header>
              <div class="panel block__card">
                <div class="field-grid">
                  <ParamField
                    v-for="param in listSwitches"
                    :key="param.name"
                    :param="param"
                    :error="fieldErrors[param.name]"
                    :model-value="store.values[param.name]"
                    :disabled="
                      (param.name === 'OVERALL_TOPS' && !store.values.OVERALL_ENABLED) ||
                      (param.name.startsWith('TOP_') && !store.values.COUNTRY_FILTERS)
                    "
                    @update:model-value="update(param, $event)"
                  />
                </div>

                <div class="country-block">
                  <p class="group-note">
                    各国列表条数
                    <HintIcon
                      content="仅开启「生成国家列表」时生效；0 表示该国不生成。"
                      label="查看各国列表条数说明"
                    />
                  </p>
                  <div class="field-grid">
                    <ParamField
                      v-for="param in countryTops"
                      :key="param.name"
                      :param="param"
                      :error="fieldErrors[param.name]"
                      :model-value="store.values[param.name]"
                      :disabled="!store.values.COUNTRY_FILTERS"
                      @update:model-value="update(param, $event)"
                    />
                  </div>
                </div>
              </div>
            </section>

            <section class="block">
              <header class="block__head">
                <el-icon><EditPen /></el-icon><span>文件名调整</span>
                <HintIcon
                  placement="bottom"
                  content="留空或使用默认名时，自动沿用默认文件名。"
                  label="查看文件名规则"
                />
              </header>
              <div class="panel block__card">
                <ArtifactNamesEditor />
              </div>
            </section>
          </div>
        </el-tab-pane>

        <el-tab-pane label="仓库设置" name="publish" lazy>
          <div class="config-split">
            <section class="block">
              <header class="block__head">
                <el-icon><Upload /></el-icon><span>仓库设置</span>
              </header>
              <div class="panel block__card">
                <div class="field-grid">
                  <ParamField
                    v-for="param in paramsFor('发布')"
                    :key="param.name"
                    :param="param"
                    :error="fieldErrors[param.name]"
                    :model-value="store.values[param.name]"
                    @update:model-value="update(param, $event)"
                  />
                </div>
              </div>
            </section>

            <section class="block">
              <header class="block__head">
                <el-icon><Files /></el-icon><span>推送列表</span>
                <HintIcon
                  placement="bottom"
                  content="关闭的列表仍会生成产物，只是不推送到仓库。"
                  label="查看推送列表说明"
                />
              </header>
              <div class="panel block__card">
                <PushListsEditor />
              </div>
            </section>
          </div>
        </el-tab-pane>

        <el-tab-pane label="代理设置" name="proxy" lazy>
          <section class="block block--medium">
            <header class="block__head">
              <el-icon><Share /></el-icon><span>代理设置</span>
            </header>
            <div class="panel block__card">
              <div class="field-grid">
                <ParamField
                  v-for="param in paramsFor('网络代理')"
                  :key="param.name"
                  :param="param"
                  :error="fieldErrors[param.name]"
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
        v-if="store.dirty && !['library', 'locations', 'schedule'].includes(activeTab)"
        class="actionbar"
      >
        <span class="muted">
          {{ store.dirty ? `未保存 ${store.dirtyCount} 项` : "没有未保存的修改" }}
        </span>
        <div class="actionbar__buttons">
          <el-button :disabled="!store.dirty" @click="diffVisible = true">查看变更</el-button>
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
        <el-table-column prop="id" label="版本" :width="versionWidth('版本') ?? 70" align="center" />
        <el-table-column label="时间" :width="versionWidth('时间') ?? 180">
          <template #default="{ row }"><span class="mono">{{ formatTime(row.created_at, String(store.values.TZ ?? "") || undefined) }}</span></template>
        </el-table-column>
        <el-table-column prop="actor" label="操作者" :width="versionWidth('操作者') ?? 90" align="center" />
        <el-table-column prop="diff" label="变更（已脱敏）" :width="versionWidth('变更（已脱敏）')" min-width="240">
          <template #default="{ row }">
            <span class="mono diff">{{ row.diff }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" :width="versionWidth('操作') ?? 90" align="center">
          <template #default="{ row }">
            <el-button size="small" @click="rollback(row.id)">回滚</el-button>
          </template>
        </el-table-column>
      </el-table>
      <EmptyState v-else title="尚无配置版本" description="每次成功保存都会生成一个可回滚版本" />
    </el-drawer>

    <el-drawer v-model="diffVisible" title="未保存的修改" size="52%">
      <el-table v-if="store.diff.length" :data="store.diff" size="small" border>
        <el-table-column prop="label" label="参数" min-width="160" />
        <el-table-column label="原值" min-width="160">
          <template #default="{ row }"><span class="mono">{{ valueText(row.old) }}</span></template>
        </el-table-column>
        <el-table-column label="新值" min-width="160">
          <template #default="{ row }"><span class="mono">{{ valueText(row.new) }}</span></template>
        </el-table-column>
        <el-table-column label="生效方式" width="120">
          <template #default="{ row }">{{ effectLabel(row.effect) }}</template>
        </el-table-column>
      </el-table>
      <EmptyState v-else compact title="没有未保存的修改" description="修改参数后，这里会列出差异" />
      <p class="muted diff-note">
        这里只展示尚未保存的差异；保存后仍会按哈希锁、校验、投影与回读核对逐步执行。
      </p>
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
/* 两列等宽卡片：整体限宽，随窗口缩放而不出现孤立窄卡 */
.config-pair {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-5);
  align-items: start;
  max-width: 1104px;
  margin-inline: auto;
}

/* 宽表单 + 窄列表：按 1.75 : 1 分配，同样整体限宽 */
.config-split {
  display: grid;
  grid-template-columns: minmax(0, 1.75fr) minmax(0, 1fr);
  gap: var(--space-5);
  align-items: start;
  max-width: 1020px;
  margin-inline: auto;
}

@media (max-width: 900px) {
  .config-pair,
  .config-split {
    grid-template-columns: minmax(0, 1fr);
    max-width: none;
  }
}

.field-errors {
  margin-bottom: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border: 1px solid color-mix(in srgb, var(--danger) 45%, var(--border));
  background: color-mix(in srgb, var(--danger) 8%, var(--surface));
  border-radius: var(--radius-md);
  font-size: var(--fs-body);
}

.field-errors ul {
  margin: 6px 0 0;
  padding-left: 18px;
}

.config-tabs :deep(.el-tabs__content) {
  padding-top: 0;
}

/* 探测 / 校验与采样：两张等宽卡片并排居中，卡内字段一行一个 */
.scanner-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 360px));
  justify-content: center;
  gap: var(--space-5);
  align-items: start;
}

.scanner-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

@media (max-width: 900px) {
  .scanner-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

/* 12 列栅格：字段按内容类型占不同跨度，数字紧凑、短文本适中、长 URL 整行 */
.field-grid {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 20px 12px;
  align-items: start;
}

.field-grid :deep(.field--full) {
  grid-column: 1 / -1;
}

.field-grid :deep(.field--half) {
  grid-column: span 6;
}

.field-grid :deep(.field--medium) {
  grid-column: span 4;
}

.field-grid :deep(.field--short) {
  grid-column: span 3;
}

.field-grid :deep(.field--compact) {
  grid-column: span 4;
}

.field-grid :deep(.field--third) {
  grid-column: span 4;
}

/* 开关类字段横跨整行，形成「设置项」式的一行一项 */
.field-grid :deep(.field--switch) {
  grid-column: 1 / -1;
}

.country-block {
  margin-top: var(--space-5);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-soft);
}

.group-note {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 var(--space-4);
  color: var(--text);
  font-size: var(--fs-label);
  font-weight: 550;
  line-height: 20px;
}

@media (max-width: 1199px) {
  .field-grid :deep(.field--compact),
  .field-grid :deep(.field--short),
  .field-grid :deep(.field--third),
  .field-grid :deep(.field--medium) {
    grid-column: span 6;
  }
}

@media (max-width: 719px) {
  .field-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .field-grid :deep(.field) {
    grid-column: 1 / -1;
  }
}

.diff {
  font-size: var(--fs-micro);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.diff-note {
  margin: var(--space-4) 0 0;
  font-size: var(--fs-meta);
  line-height: 18px;
}
</style>
