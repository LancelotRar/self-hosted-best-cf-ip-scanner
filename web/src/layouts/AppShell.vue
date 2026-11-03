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
  const forward = event.key === "ArrowDown" || event.key === "ArrowRight";
  const back = event.key === "ArrowUp" || event.key === "ArrowLeft";
  if (!forward && !back) return;
  event.preventDefault();
  const delta = forward ? 1 : -1;
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
    <aside class="sidebar">
      <RouterLink :to="{ name: 'overview' }" class="brand" aria-label="回到总览">
        <span class="brand__mark" aria-hidden="true">CF</span>
        <span class="brand__text">
          <strong>Cloudflare 优选 IP 扫描器</strong>
          <small>项目专属运维面板</small>
        </span>
      </RouterLink>

      <nav class="nav" aria-label="主导航">
        <RouterLink
          v-for="(tab, index) in tabs"
          :key="tab.name"
          :to="{ name: tab.name }"
          class="nav__item"
          active-class="nav__item--active"
          data-tab
          @keydown="onTabKey($event, index)"
        >
          {{ tab.label }}
        </RouterLink>
      </nav>

      <div class="sidebar__foot">
        <div class="status-line" role="status" aria-live="polite">
          <StatusPill :tone="scannerMeta.tone" :label="scannerMeta.label" />
          <StatusPill
            :tone="running ? 'info' : 'neutral'"
            :label="running ? '运行中' : '空闲'"
            :pulse="running"
          />
        </div>
        <p class="status-meta muted">
          更新 <span class="mono">{{ formatClock(updatedAt) }}</span>
          <span v-if="stale" class="status-stale">· 数据可能过期</span>
        </p>
        <p v-if="scannerReason" class="status-reason muted" :title="scannerReason">
          {{ scannerReason }}
        </p>

        <div class="sidebar__actions">
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
            <el-button text class="account">
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
      </div>
    </aside>

    <div class="content">
      <main class="main">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<style scoped>
.shell {
  display: flex;
  min-height: 100vh;
  background: var(--bg);
}

.sidebar {
  position: sticky;
  top: 0;
  flex: 0 0 216px;
  width: 216px;
  height: 100vh;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-3);
  background: var(--surface);
  border-right: 1px solid var(--border);
  z-index: 30;
}

.brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0 var(--space-1);
}

.brand__mark {
  display: inline-grid;
  place-items: center;
  flex: 0 0 auto;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background: var(--primary);
  color: var(--on-primary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.brand__text {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
  min-width: 0;
}

.brand__text strong {
  font-size: 12px;
  font-weight: 600;
}

.brand__text small {
  color: var(--text-muted);
  font-size: 11px;
}

.nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
  flex: 1;
  margin: 0 calc(var(--space-1) * -1);
  padding: 0 var(--space-1);
}

.nav__item {
  position: relative;
  display: flex;
  align-items: center;
  height: 38px;
  padding: 0 var(--space-3);
  border-radius: var(--radius-sm);
  border-left: 2px solid transparent;
  color: var(--text-muted);
  font-size: 13px;
  transition: background-color var(--dur-fast) var(--ease),
    color var(--dur-fast) var(--ease);
}

.nav__item:hover {
  background: var(--surface-2);
  color: var(--text);
}

.nav__item--active {
  background: color-mix(in srgb, var(--primary) 14%, var(--surface));
  border-left-color: var(--primary);
  color: var(--text);
  font-weight: 600;
}

.sidebar__foot {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-top: var(--space-3);
  border-top: 1px solid var(--border);
}

.status-line {
  display: flex;
  gap: var(--space-1);
  flex-wrap: wrap;
}

.status-meta {
  margin: 0;
  font-size: 11px;
  line-height: 16px;
}

.status-stale {
  color: var(--warning);
}

.status-reason {
  margin: 0;
  font-size: 11px;
  line-height: 16px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.sidebar__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: var(--space-1);
}

.account {
  padding-left: 4px;
  padding-right: 4px;
}

.content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.main {
  flex: 1;
}

/* 窄屏：侧栏改为横向顶部条，标签仍可横向滚动 */
@media (max-width: 959px) {
  .shell {
    display: block;
  }

  .sidebar {
    position: sticky;
    top: 0;
    width: auto;
    height: auto;
    flex-direction: row;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    border-right: 0;
    border-bottom: 1px solid var(--border);
  }

  .brand__text {
    display: none;
  }

  .nav {
    flex-direction: row;
    flex: 1;
    margin: 0;
    padding: 0;
    overflow-x: auto;
    overflow-y: hidden;
    gap: 2px;
  }

  .nav::-webkit-scrollbar {
    height: 0;
  }

  .nav__item {
    height: 36px;
    padding: 0 var(--space-3);
    border-left: 0;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    white-space: nowrap;
  }

  .nav__item--active {
    background: none;
    border-bottom-color: var(--primary);
  }

  .sidebar__foot {
    flex-direction: row;
    align-items: center;
    gap: var(--space-2);
    padding-top: 0;
    border-top: 0;
  }

  .status-meta,
  .status-reason {
    display: none;
  }

  .sidebar__actions {
    margin-top: 0;
    gap: var(--space-1);
  }
}

@media (max-width: 639px) {
  .status-line .pill:last-child {
    display: none;
  }
}
</style>
