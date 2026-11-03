<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { Document, Odometer, Operation, Setting, VideoPlay } from "@element-plus/icons-vue";
import { useRouter } from "vue-router";

import { get } from "../api";
import TopActions from "../components/TopActions.vue";
import { useAuthStore } from "../stores/auth";
import type { Overview } from "../types";

const tabs = [
  { name: "overview", label: "总览", icon: Odometer },
  { name: "config", label: "参数", icon: Setting },
  { name: "runs", label: "运行", icon: VideoPlay },
  { name: "logs", label: "日志", icon: Document },
  { name: "settings", label: "设置", icon: Operation },
] as const;

const auth = useAuthStore();
const router = useRouter();

const scanner = ref("unknown");
const scannerReason = ref("");
const running = ref(false);
let timer: number | undefined;

const online = computed(() => scanner.value === "running");
const statusText = computed(() => {
  if (scanner.value === "unknown") return "状态未知";
  if (!online.value) return "扫描器离线";
  return running.value ? "扫描器在线 · 运行中" : "扫描器在线 · 空闲";
});

async function refresh() {
  try {
    const data = await get<Overview>("/api/overview");
    scanner.value = data.scanner.state;
    scannerReason.value = data.scanner.reason ?? "";
    running.value = Boolean(data.running);
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
  timer = window.setInterval(() => void refresh(), 30_000);
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

      <footer class="sidebar__foot">
        <div
          class="scanner-state"
          :class="online ? 'scanner-state--on' : 'scanner-state--off'"
          :title="scannerReason || statusText"
          role="status"
          aria-live="polite"
        >
          <span class="scanner-state__dot" aria-hidden="true" />
          <span class="scanner-state__text">{{ statusText }}</span>
        </div>

        <TopActions class="footer-actions" />

        <div class="footer-user">
          <span class="footer-user__name">ADMIN</span>
          <button type="button" class="footer-logout" @click="logout">退出登录</button>
        </div>
      </footer>
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
  overflow-y: auto;
  flex: 1;
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
  align-items: center;
  gap: 10px;
  padding: 14px 10px 16px;
  border-top: 1px solid var(--border-soft);
  text-align: center;
}

.scanner-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  width: 100%;
  font-size: 12px;
}

.scanner-state__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex: 0 0 auto;
}

.scanner-state--on .scanner-state__dot {
  background: var(--success);
  box-shadow: 0 0 0 0 color-mix(in srgb, var(--success) 55%, transparent);
  animation: breathe-ok 2.2s ease-out infinite;
}

.scanner-state--on .scanner-state__text {
  color: var(--text-muted);
}

.scanner-state--off .scanner-state__dot {
  background: var(--danger);
  box-shadow: 0 0 0 0 color-mix(in srgb, var(--danger) 55%, transparent);
  animation: breathe-bad 1.6s ease-out infinite;
}

.scanner-state--off .scanner-state__text {
  color: var(--danger);
}

.footer-actions {
  justify-content: center;
  width: 100%;
  gap: 8px;
}

.footer-user {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  gap: 10px;
  font-size: 11.5px;
}

.footer-user__name {
  font-family: var(--font-mono);
  letter-spacing: 0.08em;
  color: var(--text-faint);
}

.footer-logout {
  padding: 0;
  border: 0;
  background: none;
  color: var(--text-muted);
  font: inherit;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.footer-logout:hover {
  color: var(--text);
}

@keyframes breathe-ok {
  0% {
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--success) 55%, transparent);
  }
  70% {
    box-shadow: 0 0 0 6px transparent;
  }
  100% {
    box-shadow: 0 0 0 0 transparent;
  }
}

@keyframes breathe-bad {
  0% {
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--danger) 55%, transparent);
  }
  70% {
    box-shadow: 0 0 0 6px transparent;
  }
  100% {
    box-shadow: 0 0 0 0 transparent;
  }
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
    flex-direction: row;
    margin: 0;
    padding: 0;
    overflow-x: auto;
    overflow-y: hidden;
    gap: 2px;
  }

  .brand__text {
    display: none;
  }

  .nav__item {
    padding: 9px var(--space-3);
    border-bottom: 2px solid transparent;
    border-radius: 0;
    white-space: nowrap;
  }

  .nav__item--active {
    background: none;
    border-bottom-color: var(--primary);
  }

  .nav__icon {
    display: none;
  }

  .sidebar__foot {
    order: 2;
    margin-left: auto;
    flex-direction: row;
    gap: 10px;
    padding: 0;
    border-top: 0;
  }

  .scanner-state__text {
    display: none;
  }

  .footer-user__name {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .scanner-state__dot {
    animation: none !important;
  }
}
</style>
