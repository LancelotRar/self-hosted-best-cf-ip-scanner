<script setup lang="ts">
import {
  Lock,
  RefreshLeft,
  Tools,
  VideoPause,
  VideoPlay,
} from "@element-plus/icons-vue";
import { onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { get, post } from "../api";
import EmptyState from "../components/EmptyState.vue";
import ErrorState from "../components/ErrorState.vue";
import PageHeader from "../components/PageHeader.vue";

interface AuditItem {
  id: number;
  at: string;
  actor: string;
  action: string;
  detail: string;
  ip: string;
}

const activeTab = ref("account");

const currentPassword = ref("");
const newPassword = ref("");
const confirmPassword = ref("");
const passwordError = ref("");
const passwordOk = ref("");
const savingPassword = ref(false);

const audits = ref<AuditItem[]>([]);
const auditError = ref("");
const page = ref(1);
const total = ref(0);
const pageSize = 50;

const info = ref<Record<string, unknown> | null>(null);
const infoError = ref("");
const busy = ref("");

const labels: Record<string, string> = { restart: "重启", stop: "停止", start: "启动" };

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

async function loadInfo() {
  infoError.value = "";
  try {
    info.value = await get<Record<string, unknown>>("/api/system/info");
  } catch (exception) {
    infoError.value = (exception as Error).message;
  }
}

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

function formatTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false });
}

onMounted(async () => {
  await loadAudit();
  await loadInfo();
});
</script>

<template>
  <section class="page">
    <PageHeader
      title="系统"
      subtitle="账号、审计、容器操作与版本信息"
      :icon="Tools"
    />

    <el-tabs v-model="activeTab">
      <el-tab-pane label="账号" name="account">
        <section class="panel form-panel">
          <header class="panel__head">修改密码</header>
          <div class="panel__body stack">
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
          <section class="panel">
            <div class="panel__body">
          <el-table v-if="audits.length" :data="audits" size="small">
            <el-table-column label="时间" width="180">
              <template #default="{ row }">{{ formatTime(row.at) }}</template>
            </el-table-column>
            <el-table-column prop="actor" label="操作者" width="90" />
            <el-table-column prop="action" label="动作" width="170">
              <template #default="{ row }"><span class="mono">{{ row.action }}</span></template>
            </el-table-column>
            <el-table-column prop="detail" label="详情" min-width="220" />
            <el-table-column prop="ip" label="来源" width="110">
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
        <section class="panel">
          <header class="panel__head">扫描容器</header>
          <div class="panel__body stack">
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
        <section v-else class="panel">
          <header class="panel__head">版本信息</header>
          <div class="panel__body">
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
            <p class="muted about-hint">
              忘记密码时在宿主机执行：
              <code class="mono">docker compose exec panel python -m panel.cli reset-password</code>
            </p>
            <p class="muted">配置版本与审计记录都会保留；不要把删除 panel.db 当作恢复手段。</p>
          </div>
        </section>
      </el-tab-pane>
    </el-tabs>
  </section>
</template>

<style scoped>
.form-panel {
  max-width: 640px;
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
