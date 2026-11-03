<script setup lang="ts">
import { computed } from "vue";

import type { SaveResult } from "../types";
import { effectLabel, formatTime } from "../utils/format";
import StatusPill from "./StatusPill.vue";

const props = defineProps<{ result: SaveResult | null }>();

const emit = defineEmits<{
  close: [];
  restart: [];
  verify: [];
  run: [];
}>();

const status = computed(() => {
  switch (props.result?.verification.status) {
    case "verified":
      return { tone: "success" as const, label: "已核对通过" };
    case "mismatch":
      return { tone: "danger" as const, label: "核对不一致" };
    case "restart_required":
      return { tone: "warning" as const, label: "需重启扫描容器" };
    case "unavailable":
      return { tone: "warning" as const, label: "当前无法核对" };
    default:
      return { tone: "neutral" as const, label: "—" };
  }
});

const canRestart = computed(
  () => props.result?.verification.status === "restart_required",
);
</script>

<template>
  <section v-if="result" class="result" aria-live="polite">
    <header class="result__head">
      <div class="row">
        <strong>保存结果</strong>
        <StatusPill
          :tone="result.written ? 'success' : 'neutral'"
          :label="result.written ? '已写入' : '无变化'"
        />
        <StatusPill :tone="status.tone" :label="status.label" />
      </div>
      <el-button text @click="emit('close')">关闭</el-button>
    </header>

    <dl class="result__facts">
      <div>
        <dt>下次执行</dt>
        <dd class="mono">{{ formatTime(result.next_run) }}</dd>
      </div>
      <div>
        <dt>调度热重载</dt>
        <dd>{{ result.effects.schedule_reloaded ? "已重载" : "未变化 / 待 watcher" }}</dd>
      </div>
      <div v-if="result.effects.restart_required.length">
        <dt>需重启参数</dt>
        <dd class="mono">{{ result.effects.restart_required.join(", ") }}</dd>
      </div>
      <div v-if="result.effects.next_round.length">
        <dt>下一轮生效</dt>
        <dd class="mono">{{ result.effects.next_round.join(", ") }}</dd>
      </div>
    </dl>

    <el-table border v-if="result.changed.length" :data="result.changed" size="small" class="result__table">
      <el-table-column prop="name" label="参数" min-width="240" />
      <el-table-column label="原值" min-width="160">
        <template #default="{ row }">
          <span class="mono">{{ row.old ?? "—" }}</span>
        </template>
      </el-table-column>
      <el-table-column label="新值" min-width="160">
        <template #default="{ row }">
          <span class="mono">{{ row.new ?? "—" }}</span>
        </template>
      </el-table-column>
      <el-table-column label="生效方式" min-width="140">
        <template #default="{ row }">{{ effectLabel(row.effect) }}</template>
      </el-table-column>
    </el-table>

    <div
      v-if="result.verification.status === 'mismatch'"
      class="result__alert result__alert--danger"
      role="alert"
    >
      <strong>扫描器读到的值与本文件不一致</strong>
      <ul>
        <li v-for="detail in result.verification.details" :key="detail.name">
          <span class="mono">{{ detail.name }}</span>：期望
          <span class="mono">{{ detail.expected }}</span>，实际
          <span class="mono">{{ detail.actual }}</span>
        </li>
      </ul>
    </div>

    <div v-if="result.warnings.length" class="result__alert result__alert--warning">
      <strong>提示</strong>
      <ul>
        <li v-for="warning in result.warnings" :key="warning">{{ warning }}</li>
      </ul>
    </div>

    <div class="result__actions">
      <el-button size="small" @click="emit('verify')">重新核对</el-button>
      <el-button size="small" @click="emit('run')">立即执行一轮</el-button>
      <el-button v-if="canRestart" size="small" type="warning" @click="emit('restart')">
        重启扫描容器
      </el-button>
    </div>
  </section>
</template>

<style scoped>
.result {
  margin-top: var(--space-4);
  padding: var(--space-4);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}

.result__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.result__facts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-3);
  margin: var(--space-4) 0 0;
  padding: var(--space-3);
  background: var(--surface-2);
  border-radius: var(--radius-sm);
}

.result__facts dt {
  color: var(--text-muted);
  font-size: 12px;
}

.result__facts dd {
  margin: 2px 0 0;
  font-size: 13px;
  overflow-wrap: anywhere;
}

.result__table {
  margin-top: var(--space-3);
}

.result__alert {
  margin-top: var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  font-size: 13px;
}

.result__alert ul {
  margin: 6px 0 0;
  padding-left: 18px;
}

.result__alert--danger {
  border-color: color-mix(in srgb, var(--danger) 45%, var(--border));
  background: color-mix(in srgb, var(--danger) 8%, var(--surface));
}

.result__alert--warning {
  border-color: color-mix(in srgb, var(--warning) 45%, var(--border));
  background: color-mix(in srgb, var(--warning) 8%, var(--surface));
}

.result__actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-top: var(--space-3);
}
</style>
