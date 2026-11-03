<script setup lang="ts">
import { onMounted, ref } from "vue";

import { get } from "../api";
import type { Overview } from "../types";

const data = ref<Overview | null>(null);
const loading = ref(true);
const error = ref("");

async function load() {
  loading.value = true;
  error.value = "";
  try {
    data.value = await get<Overview>("/api/overview");
  } catch (exception) {
    error.value = (exception as Error).message || "读取总览失败";
    data.value = null;
  } finally {
    loading.value = false;
  }
}

function formatTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false });
}

function exitLabel(code: number | null | undefined): string {
  if (code === null || code === undefined) return "—";
  return code === 0 ? "成功" : `失败（${code}）`;
}

onMounted(load);
</script>

<template>
  <section class="panel-page">
    <div class="panel-page__title">
      <h1>总览</h1>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </div>

    <el-alert
      v-if="error"
      :title="error"
      type="error"
      show-icon
      :closable="false"
      class="panel-page__alert"
    >
      <template #default>
        <el-button size="small" @click="load">重试</el-button>
      </template>
    </el-alert>

    <el-skeleton v-if="loading && !data" :rows="6" animated />

    <template v-else-if="data">
      <div class="panel-grid">
        <el-card shadow="never">
          <template #header>扫描容器</template>
          <p>
            <el-tag :type="data.scanner.state === 'running' ? 'success' : 'danger'">
              {{ data.scanner.state === "running" ? "运行中" : "不可用" }}
            </el-tag>
            <span v-if="data.scanner.health" class="panel-muted">
              健康：{{ data.scanner.health }}
            </span>
          </p>
          <p v-if="data.scanner.reason" class="panel-muted">{{ data.scanner.reason }}</p>
          <p class="panel-muted">镜像：{{ data.scanner.image ?? "—" }}</p>
          <p class="panel-muted">启动于：{{ formatTime(data.scanner.started_at) }}</p>
        </el-card>

        <el-card shadow="never">
          <template #header>上次结果</template>
          <template v-if="data.last_run">
            <p>轮次：<span class="panel-mono">{{ data.last_run.run_id }}</span></p>
            <p>扫描：{{ exitLabel(data.last_run.scan_exit) }} · 发布：{{ exitLabel(data.last_run.publish_exit) }}</p>
            <p class="panel-muted">结束于：{{ formatTime(data.last_run.finished_at) }}</p>
            <p class="panel-muted">{{ data.last_run.summary ?? "无摘要" }}</p>
          </template>
          <p v-else class="panel-muted">尚无轮次记录，等待第一轮扫描。</p>
        </el-card>

        <el-card shadow="never">
          <template #header>下次执行</template>
          <ol v-if="data.next_runs.length" class="panel-runs">
            <li v-for="run in data.next_runs" :key="run">{{ formatTime(run) }}</li>
          </ol>
          <p v-else class="panel-muted">调度表达式无效或未配置。</p>
        </el-card>
      </div>

      <el-card shadow="never" class="panel-page__section">
        <template #header>生效配置摘要</template>
        <el-descriptions :column="2" border>
          <el-descriptions-item
            v-for="(value, key) in data.config_summary"
            :key="key"
            :label="String(key)"
          >
            {{ Array.isArray(value) ? value.join(",") : value }}
          </el-descriptions-item>
        </el-descriptions>
        <p class="panel-muted">参数来自 `.env`；修改后下一轮生效，调度变更会热重载。</p>
      </el-card>
    </template>
  </section>
</template>

<style scoped>
.panel-page__alert {
  margin-bottom: 16px;
}

.panel-page__section {
  margin-top: 16px;
}

.panel-runs {
  margin: 0;
  padding-left: 20px;
}
</style>
