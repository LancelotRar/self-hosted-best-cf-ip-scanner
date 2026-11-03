<script setup lang="ts">
import { computed } from "vue";

import type { SaveResult } from "../types";

const props = defineProps<{ result: SaveResult | null }>();

const emit = defineEmits<{
  close: [];
  restart: [];
  verify: [];
  run: [];
}>();

const verification = computed(() => props.result?.verification ?? null);

const meta = computed(() => {
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

function effectLabel(effect: string): string {
  if (effect === "restart_required") return "重启后生效";
  if (effect === "schedule_reload") return "已热重载";
  return "下一轮生效";
}

function formatTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString("zh-CN", { hour12: false });
}
</script>

<template>
  <el-card v-if="result" shadow="never" class="result">
    <template #header>
      <div class="result__head">
        <strong>保存结果</strong>
        <el-button text @click="emit('close')">关闭</el-button>
      </div>
    </template>

    <el-descriptions :column="2" border>
      <el-descriptions-item label="写入">
        <el-tag :type="result.written ? 'success' : 'info'">
          {{ result.written ? "已写入" : "无变化" }}
        </el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="核对状态">
        <el-tag :type="meta.type">{{ meta.label }}</el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="下次执行">{{ formatTime(result.next_run) }}</el-descriptions-item>
      <el-descriptions-item label="调度热重载">
        {{ result.effects.schedule_reloaded ? "已重载" : "未变化 / 待 watcher" }}
      </el-descriptions-item>
    </el-descriptions>

    <el-table v-if="result.changed.length" :data="result.changed" size="small" class="result__table">
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
      class="result__alert"
    >
      <ul>
        <li v-for="detail in verification.details" :key="detail.name">
          {{ detail.name }}：期望 {{ detail.expected }}，实际 {{ detail.actual }}
        </li>
      </ul>
    </el-alert>

    <el-alert
      v-if="result.warnings.length"
      type="warning"
      :closable="false"
      show-icon
      title="提示"
      class="result__alert"
    >
      <ul>
        <li v-for="warning in result.warnings" :key="warning">{{ warning }}</li>
      </ul>
    </el-alert>

    <div class="result__actions">
      <el-button size="small" @click="emit('verify')">重新核对</el-button>
      <el-button size="small" @click="emit('run')">立即执行一轮</el-button>
      <el-button
        v-if="verification?.status === 'restart_required'"
        size="small"
        type="warning"
        @click="emit('restart')"
      >
        重启扫描容器
      </el-button>
    </div>
  </el-card>
</template>

<style scoped>
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

.result__alert {
  margin-top: 12px;
}

.result__actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
}

ul {
  margin: 6px 0 0;
  padding-left: 18px;
}
</style>
