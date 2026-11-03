<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import EmptyState from "../components/EmptyState.vue";
import LogConsole from "../components/LogConsole.vue";
import PageHeader from "../components/PageHeader.vue";
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

const visible = computed(() => {
  const keyword = filter.value.trim();
  if (!keyword) return lines.value;
  return lines.value.filter((line) => line.includes(keyword));
});

const paused = computed(() => status.value === "paused");

function togglePause() {
  if (paused.value) resume();
  else pause();
}

function clear() {
  lines.value = [];
}

onMounted(connect);
</script>

<template>
  <section class="page">
    <PageHeader title="日志" subtitle="本项目扫描容器的实时日志；断开时显示重连状态">
      <a href="/api/logs/download?tail=5000">
        <el-button>下载最近日志</el-button>
      </a>
    </PageHeader>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="实时日志" name="live">
        <div class="toolbar">
          <el-input v-model="filter" placeholder="关键字过滤" clearable class="filter" />
          <el-button @click="togglePause">{{ paused ? "继续" : "暂停" }}</el-button>
          <el-button @click="clear">清空</el-button>
        </div>
        <LogConsole :lines="visible" :status="status" :last-received="lastReceived" height="480px" />
      </el-tab-pane>

      <el-tab-pane label="下载" name="download">
        <section class="panel">
          <div class="panel__body stack">
            <p class="muted">下载按钮在页面右上角，包含最近 5000 行容器日志。</p>
            <div>
              <a href="/api/logs/download?tail=5000">
                <el-button type="primary">下载 scanner-logs.txt</el-button>
              </a>
            </div>
            <p class="muted">下载失败时请检查扫描容器是否在线；面板会返回明确错误。</p>
          </div>
        </section>
      </el-tab-pane>
    </el-tabs>

    <EmptyState
      v-if="status === 'disconnected' && !lines.length"
      title="暂无日志连接"
      description="扫描容器不可用或连接被拒绝；恢复后会自动重连"
    />
  </section>
</template>

<style scoped>
.filter {
  max-width: 320px;
}
</style>
