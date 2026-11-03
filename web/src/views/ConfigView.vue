<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { onBeforeRouteLeave } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";

import { post } from "../api";
import ParamField from "../components/ParamField.vue";
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

const grouped = computed<Array<{ name: string; params: Param[] }>>(() => {
  const names = GROUPS[activeTab.value] ?? [];
  return names
    .map((name) => ({
      name,
      params: store.params.filter((param) => param.group === name),
    }))
    .filter((group) => group.params.length > 0);
});

const verification = computed(() => store.lastResult?.verification ?? null);

const verificationMeta = computed(() => {
  switch (verification.value?.status) {
    case "verified":
      return { type: "success" as const, label: "已核对通过" };
    case "mismatch":
      return { type: "error" as const, label: "核对不一致" };
    case "restart_required":
      return { type: "warning" as const, label: "已保存，需重启扫描容器" };
    case "unavailable":
      return { type: "warning" as const, label: "已保存，下一轮生效，当前无法核对" };
    default:
      return { type: "info" as const, label: "—" };
  }
});

const effectLabel = (effect: string) => {
  switch (effect) {
    case "restart_required":
      return "重启后生效";
    case "schedule_reload":
      return "已热重载";
    default:
      return "下一轮生效";
  }
};

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
        <el-tab-pane label="扫描参数" name="scanner">
          <el-collapse :model-value="grouped.map((group) => group.name)">
            <el-collapse-item v-for="group in grouped" :key="group.name" :name="group.name" :title="group.name">
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

        <el-tab-pane label="发布与代理" name="publish">
          <el-collapse :model-value="grouped.map((group) => group.name)">
            <el-collapse-item v-for="group in grouped" :key="group.name" :name="group.name" :title="group.name">
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

        <el-tab-pane label="只读设置" name="readonly">
          <el-alert
            type="info"
            :closable="false"
            show-icon
            title="只读参数需要手工修改 .env 并重建容器（docker compose up -d）。"
          />
          <el-collapse :model-value="grouped.map((group) => group.name)">
            <el-collapse-item v-for="group in grouped" :key="group.name" :name="group.name" :title="group.name">
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

      <el-card v-if="store.lastResult" shadow="never" class="result">
        <template #header>
          <div class="result__head">
            <strong>保存结果</strong>
            <el-button text @click="store.lastResult = null">关闭</el-button>
          </div>
        </template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="写入">
            <el-tag :type="store.lastResult.written ? 'success' : 'info'">
              {{ store.lastResult.written ? "已写入" : "无变化" }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="核对状态">
            <el-tag :type="verificationMeta.type">{{ verificationMeta.label }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="下次执行">{{ formatTime(store.lastResult.next_run) }}</el-descriptions-item>
          <el-descriptions-item label="调度热重载">
            {{ store.lastResult.effects.schedule_reloaded ? "已重载" : "未变化 / 待 watcher" }}
          </el-descriptions-item>
        </el-descriptions>

        <el-table v-if="store.lastResult.changed.length" :data="store.lastResult.changed" size="small" class="result__table">
          <el-table-column prop="name" label="参数" />
          <el-table-column prop="old" label="原值" />
          <el-table-column prop="new" label="新值" />
          <el-table-column label="生效方式">
            <template #default="{ row }">{{ effectLabel(row.effect) }}</template>
          </el-table-column>
        </el-table>

        <el-alert
          v-if="verification?.status === 'mismatch'"
          type="error"
          :closable="false"
          show-icon
          title="扫描器读到的值与本文件不一致"
          class="panel-page__alert"
        >
          <ul>
            <li v-for="detail in verification.details" :key="detail.name">
              {{ detail.name }}：期望 {{ detail.expected }}，实际 {{ detail.actual }}
            </li>
          </ul>
        </el-alert>

        <el-alert
          v-if="store.lastResult.warnings.length"
          type="warning"
          :closable="false"
          show-icon
          title="提示"
        >
          <ul>
            <li v-for="warning in store.lastResult.warnings" :key="warning">{{ warning }}</li>
          </ul>
        </el-alert>

        <el-button
          v-if="verification?.status === 'restart_required'"
          type="warning"
          :loading="restarting"
          class="result__restart"
          @click="restartScanner"
        >
          重启扫描容器使参数生效
        </el-button>
      </el-card>

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
