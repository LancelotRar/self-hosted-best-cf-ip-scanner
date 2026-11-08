<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  Brush,
  Document,
  InfoFilled,
  Link,
  Lock,
  Monitor,
  RefreshLeft,
  Timer,
  VideoPause,
  VideoPlay,
} from "@element-plus/icons-vue";

import { get, post } from "../api";
import EmptyState from "../components/EmptyState.vue";
import ErrorState from "../components/ErrorState.vue";
import PageHeader from "../components/PageHeader.vue";
import ParamField from "../components/ParamField.vue";
import { PROJECT_URL } from "../config";
import { useTheme, type Theme } from "../composables/useTheme";
import { useTableWidths } from "../composables/useTableWidths";
import { useConfigStore } from "../stores/config";
import { useUiSettings, type FontSize } from "../composables/useUiSettings";

interface AuditItem {
  id: number;
  at: string;
  actor: string;
  action: string;
  detail: string;
  ip: string;
}

const activeTab = ref("appearance");

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

function formatTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false });
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
  } catch (exception) {
    ElMessage.error((exception as Error).message);
  } finally {
    busy.value = "";
  }
}

const info = ref<Record<string, unknown> | null>(null);
const infoError = ref("");

async function loadInfo() {
  infoError.value = "";
  try {
    info.value = await get<Record<string, unknown>>("/api/system/info");
  } catch (exception) {
    infoError.value = (exception as Error).message;
  }
}

const tzParam = computed(() => config.params.find((param) => param.name === "TZ") ?? null);

function updateTz(value: unknown) {
  config.applyLocal({ TZ: value });
}

async function saveTimezone() {
  try {
    await config.save();
    ElMessage.success("时区已保存，重启扫描容器后生效");
  } catch (exception) {
    ElMessage.error((exception as Error).message);
  }
}

onMounted(async () => {
  await loadAudit();
  await loadInfo();
  await config.load().catch((exception: Error) => ElMessage.error(exception.message));
});
</script>

<template>
  <section class="page">
    <PageHeader title="设置" subtitle="时区、外观、账号、审计、容器与版本信息" />

    <el-tabs v-model="activeTab">
      <el-tab-pane label="常规" name="general">
        <section class="block">
          <header class="block__head"><el-icon><Timer /></el-icon><span>时区</span></header>
          <div class="panel block__card">
            <p class="muted settings-hint">
              影响计划任务、运行记录与日志时间；保存后需重启扫描容器生效。
            </p>
            <ErrorState v-if="!tzParam && config.lastError" :message="config.lastError.message" />
            <ParamField
              v-if="tzParam"
              :param="tzParam"
              :model-value="config.values.TZ"
              @update:model-value="updateTz"
            />
            <div class="settings-actions">
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
          </div>
        </section>
      </el-tab-pane>

      <el-tab-pane label="外观" name="appearance">
        <section class="block">
          <header class="block__head">
            <el-icon><Brush /></el-icon><span>外观</span>
            <span class="spacer" />
            <el-button size="small" @click="reset">
              <el-icon><RefreshLeft /></el-icon>
              恢复默认
            </el-button>
          </header>
          <div class="panel block__card stack">
            <div class="setting-row">
              <div class="setting-label">
                <strong>主题模式</strong>
                <p class="muted">深色适合长时间盯屏；浅色适合明亮环境。</p>
              </div>
              <el-radio-group v-model="themeValue">
                <el-radio-button value="dark">深色</el-radio-button>
                <el-radio-button value="light">浅色</el-radio-button>
              </el-radio-group>
            </div>

            <div class="setting-row">
              <div class="setting-label">
                <strong>字号</strong>
                <p class="muted">影响正文、表格、按钮与表单标签，仅保存在本浏览器。</p>
              </div>
              <el-radio-group v-model="fontValue">
                <el-radio-button value="sm">小</el-radio-button>
                <el-radio-button value="md">标准</el-radio-button>
                <el-radio-button value="lg">大</el-radio-button>
              </el-radio-group>
            </div>

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

        <section class="block">
          <header class="block__head"><el-icon><Link /></el-icon><span>项目</span></header>
          <div class="panel block__card stack">
            <p class="muted">面板与扫描器同源；问题反馈、版本说明与部署文档都在项目主页。</p>
            <div>
              <a :href="PROJECT_URL" target="_blank" rel="noopener noreferrer">
                <el-button>GitHub 项目主页</el-button>
              </a>
            </div>
            <p class="muted mono repo-url">
              github.com/LancelotRar/self-hosted-best-cf-ip-scanner
            </p>
          </div>
        </section>
      </el-tab-pane>

      <el-tab-pane label="账号" name="account">
        <section class="block">
          <header class="block__head"><el-icon><Lock /></el-icon><span>修改密码</span></header>
          <div class="panel block__card stack">
            <label class="field-label" for="current-password">当前密码</label>
            <el-input
              id="current-password"
              v-model="currentPassword"
              type="password"
              show-password
              autocomplete="current-password"
            />

            <label class="field-label" for="new-password">新密码</label>
            <el-input
              id="new-password"
              v-model="newPassword"
              type="password"
              show-password
              autocomplete="new-password"
            />

            <label class="field-label" for="confirm-password">确认新密码</label>
            <el-input
              id="confirm-password"
              v-model="confirmPassword"
              type="password"
              show-password
              autocomplete="new-password"
            />

            <p v-if="passwordError" class="form-error" role="alert">{{ passwordError }}</p>
            <p v-if="passwordOk" class="form-ok" role="status">{{ passwordOk }}</p>

            <div>
              <el-button type="primary" :loading="savingPassword" @click="changePassword">
                <el-icon><Lock /></el-icon>修改密码
              </el-button>
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
                  <template #default="{ row }">{{ formatTime(row.at) }}</template>
                </el-table-column>
                <el-table-column prop="actor" label="操作者" :width="colWidth('操作者') ?? 90" />
                <el-table-column prop="action" label="动作" :width="colWidth('动作') ?? 170">
                  <template #default="{ row }"><span class="mono">{{ row.action }}</span></template>
                </el-table-column>
                <el-table-column prop="detail" label="详情" :width="colWidth('详情')" min-width="220" />
                <el-table-column prop="ip" label="来源" :width="colWidth('来源') ?? 110">
                  <template #default="{ row }"><span class="mono">{{ row.ip }}</span></template>
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
        <section class="block">
          <header class="block__head"><el-icon><Monitor /></el-icon><span>扫描容器</span></header>
          <div class="panel block__card stack">
            <p class="muted">
              只操作本项目的扫描容器；重启/停止会中断当前这一轮，产物保留上一轮。
            </p>
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
        <section v-else class="block">
          <header class="block__head"><el-icon><InfoFilled /></el-icon><span>版本信息</span></header>
          <div class="panel block__card">
            <dl v-if="info" class="kv">
              <dt>面板版本</dt>
              <dd class="mono">{{ info.panel_version }}</dd>
              <dt>镜像</dt>
              <dd class="mono">{{ info.image }}</dd>
              <dt>Python</dt>
              <dd class="mono">{{ info.python }}</dd>
              <dt>Docker SDK</dt>
              <dd class="mono">{{ info.docker }}</dd>
            </dl>
            <p class="muted about-hint">忘记密码请联系部署管理员。</p>
            <p class="muted">配置版本与审计记录都会保留，可在面板内完成回滚与核查。</p>
          </div>
        </section>
      </el-tab-pane>
    </el-tabs>
  </section>
</template>

<style scoped>
.settings-hint {
  margin: 0 0 var(--space-3);
  font-size: 12px;
}

.settings-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.settings-panel {
  margin-bottom: var(--space-4);
}

.settings-panel:last-child {
  margin-bottom: 0;
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border);
}

.setting-label strong {
  font-size: 13px;
}

.setting-label p {
  margin: 2px 0 0;
  font-size: 12px;
  line-height: 18px;
}

.preview {
  padding: var(--space-4);
  border: 1px dashed var(--border);
  border-radius: var(--radius-md);
  background: var(--surface-2);
}

.preview__eyebrow {
  font-size: 11px;
  letter-spacing: 0.08em;
}

.preview__title {
  margin: 4px 0 0;
  font-size: 18px;
  line-height: 26px;
}

.preview__text {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 20px;
}

.preview__meta {
  margin: 8px 0 0;
  color: var(--text-muted);
  font-size: 12px;
}

.repo-url {
  font-size: 12px;
  overflow-wrap: anywhere;
}

.form-panel .el-input {
  max-width: 520px;
}

.field-label {
  font-size: 12px;
  color: var(--text-muted);
}

.form-error,
.form-ok {
  margin: 0;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  font-size: 12px;
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

.about-hint {
  margin-top: var(--space-4);
  line-height: 1.8;
}
</style>
