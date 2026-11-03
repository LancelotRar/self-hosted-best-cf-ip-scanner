<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";

import type { StreamStatus } from "../composables/useEventStream";
import { formatClock } from "../utils/format";
import StatusPill from "./StatusPill.vue";

const props = withDefaults(
  defineProps<{
    lines: string[];
    status: StreamStatus;
    lastReceived: Date | null;
      height?: string;
    ended?: boolean;
  }>(),
  { height: "420px", ended: false },
);

const box = ref<HTMLPreElement | null>(null);
const atBottom = ref(true);
const pending = ref(0);

const meta = computed(() => {
  if (props.ended) return { tone: "neutral" as const, label: "已结束" };
  switch (props.status) {
    case "live":
      return { tone: "success" as const, label: "实时" };
    case "connecting":
      return { tone: "info" as const, label: "连接中" };
    case "paused":
      return { tone: "warning" as const, label: "已暂停" };
    default:
      return { tone: "danger" as const, label: "已断开" };
  }
});

function onScroll() {
  const element = box.value;
  if (!element) return;
  const distance = element.scrollHeight - element.scrollTop - element.clientHeight;
  atBottom.value = distance < 24;
  if (atBottom.value) pending.value = 0;
}

function jumpToBottom() {
  const element = box.value;
  if (!element) return;
  element.scrollTop = element.scrollHeight;
  atBottom.value = true;
  pending.value = 0;
}

watch(
  () => props.lines.length,
  async () => {
    if (props.status === "paused") return;
    if (!atBottom.value) {
      pending.value += 1;
      return;
    }
    await nextTick();
    if (box.value) box.value.scrollTop = box.value.scrollHeight;
  },
);
</script>

<template>
  <div class="console">
    <div class="console__bar">
      <StatusPill :tone="meta.tone" :label="meta.label" :pulse="status === 'connecting'" />
      <span class="muted console__meta">
        最后接收 <span class="mono">{{ formatClock(lastReceived) }}</span>
      </span>
      <span class="muted console__meta">{{ lines.length }} 行</span>
      <span class="spacer" />
      <span class="sr-only" role="status" aria-live="polite">
        日志{{ meta.label }}，共 {{ lines.length }} 行
      </span>
    </div>

    <div class="console__frame">
      <pre
        ref="box"
        class="console__body"
        :style="{ height }"
        aria-live="off"
        tabindex="0"
        @scroll="onScroll"
      >{{ lines.join("\n") }}</pre>
      <button v-if="!atBottom" class="console__jump" type="button" @click="jumpToBottom">
        回到底部<template v-if="pending">（{{ pending }} 条新日志）</template>
      </button>
    </div>
  </div>
</template>

<style scoped>
.console {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--surface);
}

.console__bar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border);
  background: var(--surface-2);
  font-size: 12px;
}

.console__meta {
  white-space: nowrap;
}

.console__frame {
  position: relative;
  background: var(--log-bg);
}

.console__body {
  margin: 0;
  padding: var(--space-3);
  overflow: auto;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 18px;
  color: #c9d1d9;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.console__jump {
  position: absolute;
  right: 16px;
  bottom: 16px;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid var(--primary);
  background: var(--primary);
  color: var(--on-primary);
  font-size: 12px;
  cursor: pointer;
}

.console__jump:hover {
  background: var(--primary-hover);
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@media (max-width: 767px) {
  .console__body {
    height: 320px !important;
  }
}
</style>
