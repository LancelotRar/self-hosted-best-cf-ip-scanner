<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import LogConsole from "../components/LogConsole.vue";
import { useEventStream } from "../composables/useEventStream";

const activeTab = ref("live");
const filter = ref("");
const lines = ref<string[]>([]);

const { status, lastReceived, connect, pause, resume } = useEventStream(
  () => "/api/logs/stream?tail=200",
  {
    onMessage: (data) => {
      lines.value.push(data);
      if (lines.value.length > 5000) {
        lines.value = lines.value.slice(-5000);
      }
    },
  },
);

const visibleLines = computed(() => {
  const keyword = filter.value.trim();
  if (!keyword) return lines.value;
  return lines.value.filter((line) => line.includes(keyword));
});

const paused = computed(() => status.value === "paused");

function togglePause() {
  if (paused.value) {
    resume();
  } else {
    pause();
  }
}

function clear() {
  lines.value = [];
}

onMounted(connect);
</script>

<template>
  <section class="panel-page">
    <div class="panel-page__title">
      <h1>日志</h1>
      <a href="/api/logs/download?tail=5000">
        <el-button>下载最近日志</el-button>
      </a>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="实时日志" name="live">
        <div class="toolbar">
          <el-input v-model="filter" placeholder="关键字过滤" clearable class="toolbar__search" />
          <el-button @click="togglePause">{{ paused ? "继续" : "暂停" }}</el-button>
          <el-button @click="clear">清空</el-button>
        </div>
        <LogConsole :lines="visibleLines" :status="status" :last-received="lastReceived" />
        <p class="panel-muted" v-if="status === 'disconnected'">连接已断开，正在重连…</p>
      </el-tab-pane>

      <el-tab-pane label="下载" name="download">
        <p class="panel-muted">下载按钮在页面右上角；包含最近 5000 行容器日志。</p>
      </el-tab-pane>
    </el-tabs>
  </section>
</template>

<style scoped>
.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.toolbar__search {
  max-width: 320px;
}
</style>
