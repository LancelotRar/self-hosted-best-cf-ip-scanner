<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { get } from "../api";
import { useAuthStore } from "../stores/auth";
import type { Overview } from "../types";

const tabs = [
  { name: "overview", label: "总览" },
  { name: "config", label: "参数" },
  { name: "schedule", label: "调度" },
  { name: "runs", label: "运行" },
  { name: "logs", label: "日志" },
  { name: "outputs", label: "产物" },
  { name: "library", label: "IP 库" },
  { name: "publish", label: "发布" },
  { name: "system", label: "系统" },
] as const;

const auth = useAuthStore();
const router = useRouter();

const scannerState = ref("unknown");
const scannerReason = ref("");
const lastUpdated = ref("");
let timer: number | undefined;

const online = computed(() => scannerState.value === "running");
const statusLabel = computed(() => {
  if (scannerState.value === "unknown") return "状态未知";
  return online.value ? "扫描器在线" : "扫描器离线";
});

async function refresh() {
  try {
    const data = await get<Overview>("/api/overview");
    scannerState.value = data.scanner.state;
    scannerReason.value = data.scanner.reason ?? "";
    lastUpdated.value = new Date().toLocaleTimeString("zh-CN", { hour12: false });
  } catch (error) {
    scannerState.value = "unavailable";
    scannerReason.value = (error as Error).message;
    lastUpdated.value = new Date().toLocaleTimeString("zh-CN", { hour12: false });
  }
}

async function logout() {
  try {
    await auth.logout();
  } finally {
    await router.push({ name: "login" });
  }
}

onMounted(() => {
  void refresh();
  timer = window.setInterval(() => void refresh(), 30000);
});

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer);
});
</script>

<template>
  <div class="shell">
    <header class="shell__bar">
      <div class="shell__brand">
        <span class="shell__logo">CF</span>
        <div>
          <strong>Cloudflare 优选 IP 扫描器</strong>
          <div class="panel-muted shell__subtitle">项目专属运维面板</div>
        </div>
      </div>

      <div class="shell__status" role="status" aria-live="polite">
        <el-tag :type="online ? 'success' : 'danger'" effect="dark">{{ statusLabel }}</el-tag>
        <span class="panel-muted" v-if="scannerReason">原因：{{ scannerReason }}</span>
        <span class="panel-muted" v-if="lastUpdated">最后更新 {{ lastUpdated }}</span>
      </div>

      <el-dropdown trigger="click">
        <el-button text>
          {{ auth.username ?? "账号" }}
          <span aria-hidden="true">▾</span>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item @click="router.push({ name: 'system' })">账号与系统</el-dropdown-item>
            <el-dropdown-item divided @click="logout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </header>

    <nav class="shell__tabs" aria-label="主导航">
      <RouterLink
        v-for="tab in tabs"
        :key="tab.name"
        :to="{ name: tab.name }"
        class="shell__tab"
        active-class="shell__tab--active"
      >
        {{ tab.label }}
      </RouterLink>
    </nav>

    <main class="shell__main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.shell__bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 20px;
  background: var(--panel-surface);
  border-bottom: 1px solid var(--panel-border);
}

.shell__brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.shell__logo {
  display: inline-grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  background: var(--panel-brand);
  color: #fff;
  font-weight: 700;
}

.shell__subtitle {
  font-size: 12px;
}

.shell__status {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: auto;
  font-size: 12px;
}

.shell__tabs {
  display: flex;
  gap: 4px;
  padding: 0 12px;
  overflow-x: auto;
  background: var(--panel-surface);
  border-bottom: 1px solid var(--panel-border);
}

.shell__tab {
  flex: 0 0 auto;
  padding: 12px 16px;
  border-bottom: 2px solid transparent;
  color: var(--panel-muted);
  white-space: nowrap;
}

.shell__tab:hover {
  color: var(--panel-text);
}

.shell__tab--active {
  color: var(--panel-brand);
  border-bottom-color: var(--panel-brand);
  font-weight: 600;
}

.shell__main {
  flex: 1;
}
</style>
