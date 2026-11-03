<script setup lang="ts">
import { nextTick, ref, watch } from "vue";

import type { StreamStatus } from "../composables/useEventStream";

const props = defineProps<{
  lines: string[];
  status: StreamStatus;
  lastReceived: Date | null;
}>();

const box = ref<HTMLPreElement | null>(null);

const statusMeta: Record<StreamStatus, { type: "success" | "warning" | "info" | "danger"; label: string }> = {
  live: { type: "success", label: "实时" },
  connecting: { type: "info", label: "连接中" },
  paused: { type: "warning", label: "已暂停" },
  disconnected: { type: "danger", label: "已断开" },
};

watch(
  () => props.lines.length,
  async () => {
    if (props.status === "paused") return;
    await nextTick();
    if (box.value) box.value.scrollTop = box.value.scrollHeight;
  },
);
</script>

<template>
  <div class="console">
    <div class="console__bar">
      <el-tag :type="statusMeta[status].type" effect="dark">{{ statusMeta[status].label }}</el-tag>
      <span class="panel-muted" v-if="lastReceived">
        最后接收 {{ lastReceived.toLocaleTimeString("zh-CN", { hour12: false }) }}
      </span>
      <span class="panel-muted">共 {{ lines.length }} 行</span>
    </div>
    <pre ref="box" class="console__body panel-mono" aria-live="polite" aria-atomic="false">{{
      lines.join("\n")
    }}</pre>
  </div>
</template>

<style scoped>
.console__bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  font-size: 12px;
}

.console__body {
  margin: 0;
  height: 420px;
  overflow: auto;
  padding: 12px;
  background: #0d1117;
  color: #c9d1d9;
  border-radius: 8px;
  font-size: 12px;
}
</style>
