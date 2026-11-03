<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import {
  DataLine,
  Document,
  FolderOpened,
  Odometer,
  Operation,
  Setting,
  Upload,
  VideoPlay,
} from "@element-plus/icons-vue";
import { useRouter } from "vue-router";

import { get } from "../api";
import StatusPill from "../components/StatusPill.vue";
import { useAuthStore } from "../stores/auth";
import type { Overview } from "../types";
import { formatClock } from "../utils/format";

const tabs = [
  { name: "overview", label: "总览", icon: Odometer },
  { name: "config", label: "参数", icon: Setting },
  { name: "runs", label: "运行", icon: VideoPlay },
  { name: "logs", label: "日志", icon: Document },
  { name: "outputs", label: "产物", icon: FolderOpened },
  { name: "library", label: "IP 库", icon: DataLine },
  { name: "publish", label: "发布", icon: Upload },
  { name: "settings", label: "设置", icon: Operation },
] as const;

const auth = useAuthStore();
const router = useRouter();

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
          <strong>CF IP 扫描器</strong>
          <small>项目运维面板</small>
        </span>
      </RouterLink>

      <nav class="nav" aria-label="主导航">
        <RouterLink
          v-for="(tab, index) in tabs"
          :key="tab.name"
          :to="{ name: tab.name }"
          class="nav__item"
          exact-active-class="nav__item--active"
          data-tab
          @keydown="onTabKey($event, index)"
        >
          <el-icon class="nav__icon" :size="16" aria-hidden="true">
            <component :is="tab.icon" />
          </el-icon>
          <span>{{ tab.label }}</span>
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
  flex: 0 0 208px;
  width: 208px;
  height: 100vh;
  display: flex;
  flex-direction: column;
  padding: 0;
  background: var(--surface);
  border-right: 1px solid var(--border);
  z-index: 30;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px 18px 16px;
  border-bottom: 1px solid var(--border-soft);
}

.brand__mark {
  display: inline-grid;
  place-items: center;
  flex: 0 0 auto;
  width: 30px;
  height: 30px;
  border-radius: 7px;
  background: var(--primary);
  color: var(--on-primary);
  font-size: 11px;
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
  font-size: 15px;
  font-weight: 650;
  letter-spacing: -0.01em;
}

.brand__text small {
  color: var(--text-faint);
  font-family: var(--font-mono);
  font-size: 11.5px;
  margin-top: 3px;
}

.nav {
  display: flex;
  flex-direction: column;
  gap: 0;
  overflow-y: auto;
  flex: 1;
  margin: 0;
  padding: 10px 8px;
}

.nav__item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 11px;
  margin-bottom: 2px;
  border-radius: 7px;
  color: var(--text-muted);
  font-size: 13.5px;
  transition: background-color var(--dur-fast) var(--ease),
    color var(--dur-fast) var(--ease);
}

.nav__item:hover {
  background: var(--surface-2);
  color: var(--text);
}

.nav__icon {
  flex: 0 0 16px;
  color: currentColor;
  opacity: 0.82;
}

.nav__item--active {
  background: var(--primary-soft);
  color: var(--primary);
  font-weight: 550;
}

.nav__item--active .nav__icon {
  color: var(--primary);
  opacity: 1;
}

.sidebar__foot {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 10px 16px;
  border-top: 1px solid var(--border-soft);
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
  gap: var(--space-1);
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
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3) 0;
    border-right: 0;
    border-bottom: 1px solid var(--border);
  }

  .nav {
    order: 3;
    flex: 0 0 100%;
  }

  .brand__text {
    display: none;
  }

  .nav {
    flex-direction: row;
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
    padding: 9px var(--space-3);
    border-bottom: 2px solid transparent;
    border-radius: 0;
    white-space: nowrap;
  }

  .nav__icon {
    display: none;
  }

  .nav__item--active {
    background: none;
    border-bottom-color: var(--primary);
  }

  .sidebar__foot {
    order: 2;
    margin-left: auto;
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

  .nav__item {
    height: 38px;
  }
}

@media (max-width: 639px) {
  .status-line .pill:last-child {
    display: none;
  }
}
</style>
