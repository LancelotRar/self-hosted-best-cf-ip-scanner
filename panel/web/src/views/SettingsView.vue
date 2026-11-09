<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { onBeforeRouteLeave } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  Brush,
  Document,
  InfoFilled,
  Link,
  Lock,
  Monitor,
  RefreshLeft,
  VideoPause,
  VideoPlay,
} from "@element-plus/icons-vue";

import { get, post } from "../api";
import EmptyState from "../components/EmptyState.vue";
import ErrorState from "../components/ErrorState.vue";
import FormSection from "../components/FormSection.vue";
import HintIcon from "../components/HintIcon.vue";
import PageHeader from "../components/PageHeader.vue";
import ParamField from "../components/ParamField.vue";
import StatusPill from "../components/StatusPill.vue";
import UnsavedDialog from "../components/UnsavedDialog.vue";
import { PROJECT_URL } from "../config";
import { useTheme, type Theme } from "../composables/useTheme";
import { useTableWidths } from "../composables/useTableWidths";
import { useConfigStore } from "../stores/config";
import { useUiSettings, type FontSize } from "../composables/useUiSettings";
import type { Overview } from "../types";
import { formatTime } from "../utils/format";

interface AuditItem {
  id: number;
  at: string;
  actor: string;
  action: string;
  detail: string;
  ip: string;
}

const TABS = ["general", "appearance", "account", "audit", "container", "about"] as const;
type SettingsTab = (typeof TABS)[number];

const route = useRoute();
const router = useRouter();
const activeTab = ref<SettingsTab>(
  TABS.includes(String(route.query.tab) as SettingsTab)
    ? (String(route.query.tab) as SettingsTab)
    : "general",
);

const config = useConfigStore();
const { theme, set } = useTheme();
const { widthFor: colWidth, onHeaderDragEnd: onColumnDragEnd } = useTableWidths("settings-audit");
const { fontSize, setFontSize, reset } = useUiSettings();

const themeValue = computed<Theme>({
  get: () => theme.value,
  set: (value) => set(value),
});

const fontValue = computed<FontSize>({
  get: () => fontSize.value,
  set: (value) => setFontSize(value),
});

const currentPassword = ref("");
const newPassword = ref("");
const confirmPassword = ref("");
const passwordError = ref("");
const passwordOk = ref("");
const savingPassword = ref(false);

async function changePassword() {
  passwordError.value = "";
  passwordOk.value = "";
  if (newPassword.value.length < 8) {
    passwordError.value = "新密码至少 8 个字符";
    return;
  }
  if (newPassword.value !== confirmPassword.value) {
    passwordError.value = "两次输入的新密码不一致";
    return;
  }
  savingPassword.value = true;
  try {
    await post("/api/auth/password", {
      current_password: currentPassword.value,
      new_password: newPassword.value,
    });
    passwordOk.value = "密码已修改";
    currentPassword.value = "";
    newPassword.value = "";
    confirmPassword.value = "";
  } catch (exception) {
    passwordError.value = (exception as Error).message;
  } finally {
    savingPassword.value = false;
  }
}

const audits = ref<AuditItem[]>([]);
const auditError = ref("");
const page = ref(1);
const total = ref(0);
const pageSize = 50;

async function loadAudit(target = page.value) {
  auditError.value = "";
  try {
    const data = await get<{ items: AuditItem[]; page: number; total: number }>(
      `/api/audit?page=${target}`,
    );
    audits.value = data.items;
    page.value = data.page;
    total.value = data.total;
  } catch (exception) {
    auditError.value = (exception as Error).message;
    audits.value = [];
  }
}

interface SystemInfo {
  panel_version?: string;
  image?: string;
  python?: string;
  docker?: string;
  timezone?: string;
}

function formatAuditTime(value: string): string {
  return formatTime(value, info.value?.timezone);
}

const busy = ref("");
const labels: Record<string, string> = { restart: "重启", stop: "停止", start: "启动" };

async function operate(action: "restart" | "stop" | "start") {
  try {
    await ElMessageBox.confirm(
      `确认${labels[action]}扫描容器？重启/停止会中断当前这一轮扫描（最多 150s 收尾）。`,
      `${labels[action]}扫描容器`,
      { confirmButtonText: labels[action], cancelButtonText: "取消", type: "warning" },
    );
  } catch {
    return;
  }
  busy.value = action;
  try {
    await post(`/api/system/${action}`, undefined, { "X-Confirm": action });
    ElMessage.success(`已请求${labels[action]}扫描容器`);
    await loadAudit();
    await loadScanner();
  } catch (exception) {
    ElMessage.error((exception as Error).message);
  } finally {
    busy.value = "";
  }
}

const info = ref<SystemInfo | null>(null);
const infoError = ref("");

async function loadInfo() {
  infoError.value = "";
  try {
    info.value = await get<SystemInfo>("/api/system/info");
  } catch (exception) {
    infoError.value = (exception as Error).message;
  }
}

const scanner = ref<Overview | null>(null);
const scannerError = ref("");
const scannerLoading = ref(false);

async function loadScanner() {
  scannerLoading.value = true;
  scannerError.value = "";
  try {
    scanner.value = await get<Overview>("/api/overview");
  } catch (exception) {
    scannerError.value = (exception as Error).message;
  } finally {
    scannerLoading.value = false;
  }
}

const scannerOnline = computed(() => scanner.value?.scanner.state === "running");
const scannerImage = computed(() => scanner.value?.scanner.image || "镜像未知");
const scannerName = computed(() => scanner.value?.scanner.name || "扫描容器");
const scannerStateLabel = computed(() => {
  if (!scanner.value) return "未知";
  if (scannerOnline.value) return scanner.value.running ? "在线 · 运行中" : "在线 · 空闲";
  return "离线";
});

const tzParam = computed(() => config.params.find((param) => param.name === "TZ") ?? null);
const panelTimezone = computed(
  () => String(config.values.TZ ?? info.value?.timezone ?? "UTC"),
);
const nextRun = computed(() => scanner.value?.schedule?.next_runs?.[0] ?? null);

function updateTz(value: unknown) {
  config.applyLocal({ TZ: value });
}

async function saveTimezone() {
  try {
    await config.save();
    ElMessage.success("时区已保存，重启扫描容器后生效");
    await loadInfo();
  } catch (exception) {
    ElMessage.error((exception as Error).message);
  }
}

const unsavedVisible = ref(false);
const leaving = ref<((ok: boolean) => void) | null>(null);

function resolveLeave(ok: boolean) {
  unsavedVisible.value = false;
  leaving.value?.(ok);
  leaving.value = null;
}

function discardAndLeave() {
  config.cancel();
  resolveLeave(true);
}

function focusTimezone() {
  document.getElementById("param-TZ")?.focus();
}

onBeforeRouteLeave(async () => {
  if (!config.dirty) return true;
  unsavedVisible.value = true;
  return new Promise<boolean>((resolve) => {
    leaving.value = resolve;
  });
});

watch(
  () => route.query.tab,
  (value) => {
    const tab = String(value ?? "");
    if (TABS.includes(tab as SettingsTab) && tab !== activeTab.value) {
      activeTab.value = tab as SettingsTab;
    }
  },
);

watch(activeTab, (tab) => {
  if (route.query.tab === tab) return;
  void router.replace({ query: { ...route.query, tab } });
});

onMounted(async () => {
  await Promise.all([
    loadAudit(),
    loadInfo(),
    loadScanner(),
    config.load().catch((exception: Error) => ElMessage.error(exception.message)),
  ]);
});
</script>

<template>
  <section class="page">
    <PageHeader title="设置" subtitle="时区、外观、账号、审计、容器与版本信息" />

    <el-tabs v-model="activeTab">
      <el-tab-pane label="常规" name="general">
        <section class="form-shell settings-block">
          <div class="panel form-panel">
            <section class="form-section">
              <ErrorState v-if="!tzParam && config.lastError" :message="config.lastError.message" />
              <div class="form-grid">
                <ParamField
                  v-if="tzParam"
                  :param="tzParam"
                  :model-value="config.values.TZ"
                  @update:model-value="updateTz"
                />
              </div>
              <div class="form-actions">
                <span class="muted">
                  {{ config.dirty ? `未保存 ${config.dirtyCount} 项` : "没有未保存的修改" }}
                </span>
                <span class="spacer" />
                <el-button :disabled="!config.dirty" @click="config.cancel()">取消</el-button>
                <el-button
                  type="primary"
                  :disabled="!config.dirty"
                  :loading="config.saving"
                  @click="saveTimezone"
                >
                  保存
                </el-button>
              </div>
            </section>

            <FormSection
              title="运行时间"
              description="运行记录与日志按面板时区显示；浏览器时区不同也不会改变计划时间。"
            >
              <dl class="kv">
                <div class="kv__row">
                  <dt>面板时区</dt>
                  <dd class="mono">{{ panelTimezone }}</dd>
                </div>
                <div class="kv__row">
                  <dt>下一次计划</dt>
                  <dd class="mono">{{ formatTime(nextRun, panelTimezone) }}</dd>
                </div>
                <div class="kv__row">
                  <dt>扫描器</dt>
                  <dd>
                    <StatusPill
                      :tone="scannerOnline ? 'success' : 'danger'"
                      :label="scannerStateLabel"
                    />
                  </dd>
                </div>
              </dl>
            </FormSection>
          </div>
        </section>
      </el-tab-pane>

      <el-tab-pane label="外观" name="appearance">
        <div class="appearance-grid">
          <section class="block">
            <header class="block__head">
              <el-icon><Brush /></el-icon><span>外观</span>
              <span class="spacer" />
              <el-button text size="small" @click="reset">
                <el-icon><RefreshLeft /></el-icon>
                恢复默认
              </el-button>
            </header>
            <div class="panel block__card stack">
              <div class="setting-row">
                <div class="setting-label">
                  <strong>主题模式</strong>
                  <span class="setting-desc">深色适合长时间盯屏；浅色适合明亮环境。</span>
                </div>
                <el-radio-group v-model="themeValue" aria-label="主题模式">
                  <el-radio-button value="dark">深色</el-radio-button>
                  <el-radio-button value="light">浅色</el-radio-button>
                </el-radio-group>
              </div>

              <div class="setting-row">
                <div class="setting-label">
                  <strong>字号</strong>
                  <span class="setting-desc">影响正文、表格、按钮与表单标签，仅保存在本浏览器。</span>
                </div>
                <el-radio-group v-model="fontValue" aria-label="字号">
                  <el-radio-button value="sm">小</el-radio-button>
                  <el-radio-button value="md">标准</el-radio-button>
                  <el-radio-button value="lg">大</el-radio-button>
                </el-radio-group>
              </div>
            </div>
          </section>

          <section class="block">
            <header class="block__head">
              <el-icon><Monitor /></el-icon><span>预览</span>
            </header>
            <div class="panel block__card">
              <div class="preview">
                <span class="preview__eyebrow muted">预览</span>
                <h2 class="preview__title">扫描器在线 · 核对通过</h2>
                <p class="preview__text">
                  每轮扫描都会读取最新配置；保存后下一轮生效，计划任务变更立即生效。
                </p>
                <p class="preview__meta mono">2026/11/03 15:20:00 · 采样步长 256</p>
              </div>
            </div>
          </section>
        </div>
      </el-tab-pane>

      <el-tab-pane label="账号" name="account">
        <section class="block settings-block settings-block--narrow">
          <header class="block__head"><el-icon><Lock /></el-icon><span>修改密码</span></header>
          <div class="panel block__card">
            <div class="password-form">
              <label class="form-label" for="current-password">当前密码</label>
              <el-input
                id="current-password"
                v-model="currentPassword"
                type="password"
                show-password
                autocomplete="current-password"
              />

              <label class="form-label" for="new-password">新密码</label>
              <el-input
                id="new-password"
                v-model="newPassword"
                type="password"
                show-password
                autocomplete="new-password"
                aria-describedby="new-password-help"
              />
              <p id="new-password-help" class="form-help">至少 8 个字符。</p>

              <label class="form-label" for="confirm-password">确认新密码</label>
              <el-input
                id="confirm-password"
                v-model="confirmPassword"
                type="password"
                show-password
                autocomplete="new-password"
              />

              <p v-if="passwordError" class="form-error" role="alert">{{ passwordError }}</p>
              <p v-if="passwordOk" class="form-ok" role="status">{{ passwordOk }}</p>

              <div class="form-actions password-form__actions">
                <span class="spacer" />
                <el-button type="primary" :loading="savingPassword" @click="changePassword">
                  <el-icon><Lock /></el-icon>修改密码
                </el-button>
              </div>
            </div>
          </div>
        </section>
      </el-tab-pane>

      <el-tab-pane label="审计" name="audit">
        <ErrorState v-if="auditError" :message="auditError" @retry="loadAudit()" />
        <template v-else>
          <section class="block">
            <header class="block__head"><el-icon><Document /></el-icon><span>审计日志</span></header>
            <div class="panel block__card">
              <el-table border v-if="audits.length" :data="audits" size="small" @header-dragend="onColumnDragEnd">
                <el-table-column label="时间" :width="colWidth('时间') ?? 180">
                  <template #default="{ row }"><span class="mono">{{ formatAuditTime(row.at) }}</span></template>
                </el-table-column>
                <el-table-column prop="actor" label="操作者" :width="colWidth('操作者') ?? 90" align="center" />
                <el-table-column prop="action" label="动作" :width="colWidth('动作') ?? 170">
                  <template #default="{ row }"><span class="mono">{{ row.action }}</span></template>
                </el-table-column>
                <el-table-column prop="detail" label="详情" :width="colWidth('详情')" min-width="220" />
                <el-table-column prop="ip" label="来源" :width="colWidth('来源') ?? 120" align="center">
                  <template #default="{ row }"><span class="mono nowrap">{{ row.ip }}</span></template>
                </el-table-column>
              </el-table>
              <EmptyState
                v-else
                title="尚无操作记录"
                description="登录、配置保存、容器操作都会记录在这里"
                action-label="刷新"
                @action="loadAudit()"
              />
              <el-pagination
                v-if="total > pageSize"
                layout="prev, pager, next"
                :current-page="page"
                :page-size="pageSize"
                :total="total"
                @current-change="loadAudit"
              />
            </div>
          </section>
        </template>
      </el-tab-pane>

      <el-tab-pane label="容器" name="container">
        <section class="block settings-block">
          <header class="block__head">
            <el-icon><Monitor /></el-icon><span>扫描容器</span>
            <HintIcon
              placement="bottom"
              content="只操作本项目的扫描容器；重启或停止会中断当前这一轮，产物保留上一轮。"
              label="查看扫描容器说明"
            />
            <el-button text size="small" :loading="scannerLoading" @click="loadScanner">
              <el-icon><RefreshLeft /></el-icon>刷新状态
            </el-button>
          </header>
          <div class="panel block__card">
            <ErrorState v-if="scannerError" :message="scannerError" @retry="loadScanner" />
            <div v-else class="container-status">
              <StatusPill :tone="scannerOnline ? 'success' : 'danger'" :label="scannerStateLabel" />
              <div class="container-status__text">
                <strong class="mono">{{ scannerName }}</strong>
                <span class="muted mono">{{ scannerImage }}</span>
                <span v-if="!scannerOnline && scanner?.scanner.reason" class="text-danger">
                  {{ scanner.scanner.reason }}
                </span>
              </div>
            </div>
            <div class="row">
              <el-button :loading="busy === 'restart'" @click="operate('restart')">
                <el-icon><RefreshLeft /></el-icon>重启扫描容器
              </el-button>
              <el-button :loading="busy === 'stop'" @click="operate('stop')">
                <el-icon><VideoPause /></el-icon>停止
              </el-button>
              <el-button :loading="busy === 'start'" @click="operate('start')">
                <el-icon><VideoPlay /></el-icon>启动
              </el-button>
            </div>
          </div>
        </section>
      </el-tab-pane>

      <el-tab-pane label="关于" name="about">
        <ErrorState v-if="infoError" :message="infoError" @retry="loadInfo" />
        <section v-else class="block settings-block">
          <header class="block__head"><el-icon><InfoFilled /></el-icon><span>版本信息</span></header>
          <div class="panel block__card">
            <dl v-if="info" class="kv">
              <div class="kv__row">
                <dt>面板版本</dt>
                <dd class="mono">{{ info.panel_version }}</dd>
              </div>
              <div class="kv__row">
                <dt>镜像</dt>
                <dd class="mono">{{ info.image }}</dd>
              </div>
              <div class="kv__row">
                <dt>Python</dt>
                <dd class="mono">{{ info.python }}</dd>
              </div>
              <div class="kv__row">
                <dt>Docker SDK</dt>
                <dd class="mono">{{ info.docker }}</dd>
              </div>
              <div class="kv__row">
                <dt>时区</dt>
                <dd class="mono">{{ info.timezone || "—" }}</dd>
              </div>
            </dl>
            <p class="muted about-hint">忘记密码请联系部署管理员。</p>
            <p class="muted about-hint">配置版本与审计记录都会保留，可在面板内完成回滚与核查。</p>
          </div>
        </section>

        <section class="block settings-block">
          <header class="block__head"><el-icon><Link /></el-icon><span>项目</span></header>
          <div class="panel block__card">
            <div class="project-row">
              <div>
                <p class="project-row__title">面板与扫描器同源</p>
                <p class="muted project-row__desc">
                  问题反馈、版本说明与部署文档都在项目主页。
                </p>
                <p class="muted mono repo-url">
                  github.com/LancelotRar/self-hosted-best-cf-ip-scanner
                </p>
              </div>
              <a :href="PROJECT_URL" target="_blank" rel="noopener noreferrer">
                <el-button>打开 GitHub 项目主页</el-button>
              </a>
            </div>
          </div>
        </section>
      </el-tab-pane>
    </el-tabs>

    <UnsavedDialog
      v-model="unsavedVisible"
      description="有未保存的时区修改，离开后这些修改会丢失。"
      @discard="discardAndLeave"
      @stay="focusTimezone"
    />
  </section>
</template>

<style scoped>
/* 表单类页面收窄到易读宽度，避免输入框横跨整个屏幕 */
.settings-block {
  max-width: 760px;
  margin-inline: auto;
}

.settings-block--narrow {
  max-width: 520px;
}

.container-status {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding-bottom: var(--space-4);
  margin-bottom: var(--space-4);
  border-bottom: 1px solid var(--border-soft);
}

.container-status__text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  font-size: var(--fs-meta);
  overflow-wrap: anywhere;
}

.container-status__text strong {
  font-size: var(--fs-body);
}

.appearance-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr);
  gap: var(--space-5);
  align-items: start;
  max-width: var(--form-max);
  margin-inline: auto;
  margin-bottom: var(--space-6);
}

.setting-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
  gap: var(--space-5);
  padding: 4px 0 var(--space-4);
  border-bottom: 1px solid var(--border-soft);
}

.setting-row:last-child {
  padding-bottom: 4px;
  border-bottom: 0;
}

.setting-label {
  min-width: 0;
}

.setting-label strong {
  display: block;
  font-size: var(--fs-label);
  font-weight: 600;
  line-height: 20px;
}

.setting-desc {
  display: block;
  max-width: 46ch;
  margin-top: 4px;
  color: var(--text-muted);
  font-size: var(--fs-meta);
  line-height: 18px;
}

.preview {
  padding: 20px;
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
}

.preview__eyebrow {
  font-size: var(--fs-micro);
  letter-spacing: 0.08em;
}

.preview__title {
  margin: 6px 0 0;
  font-size: var(--fs-h2);
  line-height: 26px;
  letter-spacing: -0.01em;
}

.preview__text {
  margin: 6px 0 0;
  font-size: var(--fs-body);
  line-height: 20px;
}

.preview__meta {
  margin: 10px 0 0;
  color: var(--text-muted);
  font-size: var(--fs-meta);
}

.project-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-5);
  flex-wrap: wrap;
}

.project-row__title {
  margin: 0;
  font-size: var(--fs-label);
  font-weight: 600;
}

.project-row__desc {
  margin: 2px 0 0;
  font-size: var(--fs-meta);
  line-height: 18px;
}

.repo-url {
  margin: 8px 0 0;
  font-size: var(--fs-meta);
  overflow-wrap: anywhere;
}

.password-form {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-width: none;
}

.password-form .form-label:not(:first-child) {
  margin-top: 10px;
}

.password-form .form-help {
  margin-top: 0;
  margin-bottom: 4px;
}

.password-form__actions {
  margin-top: var(--space-4);
}

.form-error,
.form-ok {
  margin: 8px 0 0;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  font-size: var(--fs-meta);
}

.form-error {
  border: 1px solid color-mix(in srgb, var(--danger) 45%, var(--border));
  background: color-mix(in srgb, var(--danger) 8%, var(--surface));
}

.form-ok {
  border: 1px solid color-mix(in srgb, var(--success) 45%, var(--border));
  background: color-mix(in srgb, var(--success) 8%, var(--surface));
}

.kv {
  display: flex;
  flex-direction: column;
  margin: 0;
}

.kv__row {
  display: grid;
  grid-template-columns: 140px minmax(0, 1fr);
  gap: var(--space-4);
  padding: 10px 0;
  border-bottom: 1px solid var(--border-soft);
}

.kv__row:last-child {
  border-bottom: 0;
}

.kv dt {
  color: var(--text-muted);
  font-size: var(--fs-meta);
}

.kv dd {
  margin: 0;
  font-size: var(--fs-body);
  overflow-wrap: anywhere;
}

.about-hint {
  margin: var(--space-3) 0 0;
  font-size: var(--fs-meta);
  line-height: 1.7;
}

.nowrap {
  white-space: nowrap;
}

@media (max-width: 560px) {
  .setting-row {
    grid-template-columns: minmax(0, 1fr);
    gap: var(--space-3);
  }
}

@media (max-width: 1023px) {
  .appearance-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
