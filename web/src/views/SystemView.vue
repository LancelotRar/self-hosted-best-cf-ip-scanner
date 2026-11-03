<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { get, post } from "../api";
import EmptyState from "../components/EmptyState.vue";

interface AuditItem {
  id: number;
  at: string;
  actor: string;
  action: string;
  target: string;
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
const page = ref(1);
const total = ref(0);
const pageSize = 50;
const info = ref<Record<string, unknown> | null>(null);
const busy = ref("");

const labels: Record<string, string> = { restart: "重启", stop: "停止", start: "启动" };

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)));

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
  const data = await get<{ items: AuditItem[]; page: number; total: number }>(
    `/api/audit?page=${target}`,
  );
  audits.value = data.items;
  page.value = data.page;
  total.value = data.total;
}

async function loadInfo() {
  try {
    info.value = await get<Record<string, unknown>>("/api/system/info");
  } catch (exception) {
    ElMessage.error((exception as Error).message);
  }
}

async function operate(action: "restart" | "stop" | "start") {
  try {
    await ElMessageBox.confirm(`确认${labels[action]}扫描容器？`, "危险操作", {
      confirmButtonText: labels[action],
      cancelButtonText: "取消",
      type: "warning",
    });
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
  await loadAudit().catch((exception: Error) => ElMessage.error(exception.message));
  await loadInfo();
});
</script>

<template>
  <section class="panel-page">
    <div class="panel-page__title">
      <h1>系统</h1>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="账号" name="account">
        <el-form label-width="120px" class="form" @submit.prevent="changePassword">
          <el-form-item label="当前密码">
            <el-input v-model="currentPassword" type="password" show-password autocomplete="current-password" />
          </el-form-item>
          <el-form-item label="新密码">
            <el-input v-model="newPassword" type="password" show-password autocomplete="new-password" />
          </el-form-item>
          <el-form-item label="确认新密码">
            <el-input v-model="confirmPassword" type="password" show-password autocomplete="new-password" />
          </el-form-item>
          <el-alert v-if="passwordError" :title="passwordError" type="error" :closable="false" show-icon />
          <el-alert v-if="passwordOk" :title="passwordOk" type="success" :closable="false" show-icon />
          <el-button type="primary" :loading="savingPassword" class="form__submit" @click="changePassword">
            修改密码
          </el-button>
        </el-form>
      </el-tab-pane>

      <el-tab-pane label="审计" name="audit">
        <el-table v-if="audits.length" :data="audits" size="small">
          <el-table-column label="时间" width="180">
            <template #default="{ row }">{{ formatTime(row.at) }}</template>
          </el-table-column>
          <el-table-column prop="actor" label="操作者" width="100" />
          <el-table-column prop="action" label="动作" width="180" />
          <el-table-column prop="detail" label="详情" />
          <el-table-column prop="ip" label="来源" width="120" />
        </el-table>
        <EmptyState v-else title="尚无操作记录" description="尚无操作记录" retry-label="" />
        <el-pagination
          v-if="total > pageSize"
          layout="prev, pager, next"
          :current-page="page"
          :page-size="pageSize"
          :total="total"
          @current-change="loadAudit"
        />
      </el-tab-pane>

      <el-tab-pane label="容器" name="container">
        <p class="panel-muted">只操作本项目的扫描容器；重启会中断当前这一轮扫描。</p>
        <div class="buttons">
          <el-button :loading="busy === 'restart'" @click="operate('restart')">重启扫描容器</el-button>
          <el-button :loading="busy === 'stop'" @click="operate('stop')">停止</el-button>
          <el-button :loading="busy === 'start'" @click="operate('start')">启动</el-button>
        </div>
      </el-tab-pane>

      <el-tab-pane label="关于" name="about">
        <el-descriptions v-if="info" :column="2" border>
          <el-descriptions-item label="面板版本">{{ info.panel_version }}</el-descriptions-item>
          <el-descriptions-item label="镜像">{{ info.image }}</el-descriptions-item>
          <el-descriptions-item label="Python">{{ info.python }}</el-descriptions-item>
          <el-descriptions-item label="Docker SDK">{{ info.docker }}</el-descriptions-item>
        </el-descriptions>
        <el-alert
          type="info"
          :closable="false"
          show-icon
          title="忘记密码时可在宿主机执行：docker compose exec panel python -m panel.cli reset-password"
          class="panel-page__alert"
        />
        <p class="panel-muted">
          配置版本与审计记录都会保留；不要把删除 panel.db 当作恢复手段。
        </p>
      </el-tab-pane>
    </el-tabs>
  </section>
</template>

<style scoped>
.form {
  max-width: 560px;
}

.form__submit {
  margin-top: 12px;
}

.buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.panel-page__alert {
  margin-top: 12px;
}
</style>
