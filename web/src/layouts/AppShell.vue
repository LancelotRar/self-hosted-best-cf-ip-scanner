<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { Moon, Sunny } from "@element-plus/icons-vue";
import { useRouter } from "vue-router";

import { get } from "../api";
import StatusPill from "../components/StatusPill.vue";
import { useTheme } from "../composables/useTheme";
import { useAuthStore } from "../stores/auth";
import type { Overview } from "../types";
import { formatClock } from "../utils/format";

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
const { theme, toggle } = useTheme();

const scanner = ref("unknown");
const scannerReason = ref("");
const running = ref(false);
const updatedAt = ref<Date | null>(null);
const stale = ref(false);
let timer: number | undefined;

const scannerMeta = computed(() => {
  if (scanner.value === "running") return { tone: "success" as const, label: "扫描器在线" };
  if (scanner.value === "unknown") return { tone: "neutral" as const, label: "状态未知" };
  return { tone: "danger" as const, label: "扫描器离线" };
});

async function refresh() {
  try {
    const data = await get<Overview>("/api/overview");
    scanner.value = data.scanner.state;
    scannerReason.value = data.scanner.reason ?? "";
    running.value = Boolean(data.running);
    updatedAt.value = new Date();
    stale.value = false;
  } catch (error) {
    scanner.value = "unavailable";
    scannerReason.value = (error as Error).message;
  }
}

async function logout() {
  try {
    await auth.logout();
  } finally {
    await router.push({ name: "login" });
  }
}

function onTabKey(event: KeyboardEvent, index: number) {
  if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
  event.preventDefault();
  const delta = event.key === "ArrowRight" ? 1 : -1;
  const next = (index + delta + tabs.length) % tabs.length;
  const links = (event.currentTarget as HTMLElement)
    .closest("nav")
    ?.querySelectorAll<HTMLAnchorElement>("a[data-tab]");
  links?.[next]?.focus();
}

onMounted(() => {
  void refresh();
  timer = window.setInterval(() => {
    void refresh();
    if (updatedAt.value && Date.now() - updatedAt.value.getTime() > 90_000) {
      stale.value = true;
    }
  }, 30_000);
});

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer);
});
</script>

<template>
  <div class="shell">
    <header class="topbar">
      <RouterLink :to="{ name: 'overview' }" class="brand" aria-label="回到总览">
        <span class="brand__mark" aria-hidden="true">CF</span>
        <span class="brand__text">
          <strong>Cloudflare 优选 IP 扫描器</strong>
          <small>项目专属运维面板</small>
        </span>
      </RouterLink>

      <div class="status-strip" role="status" aria-live="polite">
        <StatusPill :tone="scannerMeta.tone" :label="scannerMeta.label" />
        <StatusPill
          :tone="running ? 'info' : 'neutral'"
          :label="running ? '轮次运行中' : '轮次空闲'"
          :pulse="running"
        />
        <span class="status-strip__time muted">
          更新 <span class="mono">{{ formatClock(updatedAt) }}</span>
        </span>
        <span v-if="stale" class="status-strip__stale">数据可能过期</span>
        <span v-if="scannerReason" class="status-strip__reason muted" :title="scannerReason">
          {{ scannerReason }}
        </span>
      </div>

      <div class="topbar__actions">
        <el-button
          text
          :aria-label="theme === 'dark' ? '切换到浅色主题' : '切换到深色主题'"
          @click="toggle"
        >
          <el-icon :size="16">
            <Sunny v-if="theme === 'dark'" />
            <Moon v-else />
          </el-icon>
        </el-button>
        <el-dropdown trigger="click">
          <el-button text>
            {{ auth.username ?? "账号" }}
            <span aria-hidden="true">▾</span>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="router.push({ name: 'system' })">
                账号与系统
              </el-dropdown-item>
              <el-dropdown-item divided @click="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <nav class="tabs" aria-label="主导航">
      <RouterLink
        v-for="(tab, index) in tabs"
        :key="tab.name"
        :to="{ name: tab.name }"
        class="tabs__item"
        active-class="tabs__item--active"
        data-tab
        @keydown="onTabKey($event, index)"
      >
        {{ tab.label }}
      </RouterLink>
    </nav>

    <main class="main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg);
}

.topbar {
  height: var(--header-h);
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: 0 var(--space-5);
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 30;
}

.brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex: 0 0 auto;
}

.brand__mark {
  display: inline-grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background: var(--primary);
  color: var(--on-primary);
  font-weight: 700;
  font-size: 12px;
  letter-spacing: 0.04em;
}

.brand__text {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.brand__text strong {
  font-size: 13px;
  font-weight: 600;
}

.brand__text small {
  color: var(--text-muted);
  font-size: 11px;
}

.status-strip {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-left: auto;
  min-width: 0;
  font-size: 12px;
}

.status-strip__time,
.status-strip__stale {
  white-space: nowrap;
}

.status-strip__stale {
  color: var(--warning);
}

.status-strip__reason {
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topbar__actions {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex: 0 0 auto;
}

.tabs {
  height: var(--tabs-h);
  display: flex;
  gap: 2px;
  padding: 0 var(--space-3);
  overflow-x: auto;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: var(--header-h);
  z-index: 25;
}

.tabs::-webkit-scrollbar {
  height: 0;
}

.tabs__item {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  padding: 0 var(--space-4);
  color: var(--text-muted);
  font-size: 13px;
  border-bottom: 2px solid transparent;
  transition: color var(--dur-fast) var(--ease),
    border-color var(--dur-fast) var(--ease);
}

.tabs__item:hover {
  color: var(--text);
}

.tabs__item--active {
  color: var(--text);
  border-bottom-color: var(--primary);
  font-weight: 600;
}

.main {
  flex: 1;
}

@media (max-width: 1023px) {
  .status-strip__reason {
    display: none;
  }
}

@media (max-width: 767px) {
  .topbar {
    padding: 0 var(--space-3);
    gap: var(--space-2);
  }

  .brand__text {
    display: none;
  }

  .status-strip__time {
    display: none;
  }

  .tabs {
    padding: 0;
  }

  .tabs__item {
    padding: 0 var(--space-3);
  }
}
</style>
