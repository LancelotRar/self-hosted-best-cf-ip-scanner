<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { Document, Odometer, Operation, Setting, VideoPlay } from "@element-plus/icons-vue";
import { useRouter } from "vue-router";

import { get } from "../api";
import TopActions from "../components/TopActions.vue";
import { useAuthStore } from "../stores/auth";
import type { Overview } from "../types";

const tabs = [
  { name: "overview", label: "信息总览", icon: Odometer },
  { name: "config", label: "参数调整", icon: Setting },
  { name: "runs", label: "手动运行", icon: VideoPlay },
  { name: "logs", label: "查看日志", icon: Document },
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
  if (scanner.value === "unknown") return "正在检测…";
  if (!online.value) return "扫描器离线";
  return running.value ? "扫描器在线 · 运行中" : "扫描器在线 · 空闲";
});
const stateTone = computed(() => {
  if (scanner.value === "unknown") return "idle";
  return online.value ? "on" : "off";
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
    <a class="skip-link" href="#main">跳到主要内容</a>
    <aside class="sidebar">
      <RouterLink :to="{ name: 'overview' }" class="brand" aria-label="回到总览">
        <span class="brand__mark" aria-hidden="true">CF</span>
        <span class="brand__text">
          <strong>优选 IP 扫描器</strong>
          <small>Cloudflare 运维面板</small>
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
          :class="`scanner-state--${stateTone}`"
          :title="scannerReason || statusText"
          role="status"
          aria-live="polite"
        >
          <span class="scanner-state__dot" aria-hidden="true" />
          <span class="scanner-state__text">{{ statusText }}</span>
        </div>

        <div class="footer-row">
          <TopActions class="footer-actions" />
          <span class="footer-user__name">admin</span>
          <button type="button" class="footer-logout" @click="logout">退出</button>
        </div>
      </footer>
    </aside>

    <div class="content">
      <main id="main" class="main" tabindex="-1">
        <Suspense>
          <RouterView />
          <template #fallback>
            <div class="route-fallback">
              <el-skeleton :rows="8" animated />
            </div>
          </template>
        </Suspense>
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

.skip-link {
  position: fixed;
  top: 8px;
  left: 8px;
  z-index: 100;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  background: var(--primary);
  color: var(--on-primary);
  font-size: var(--fs-meta);
  opacity: 0;
  pointer-events: none;
  transform: translateY(-160%);
  transition: transform var(--dur-fast) var(--ease), opacity var(--dur-fast) var(--ease);
}

.skip-link:focus-visible {
  opacity: 1;
  pointer-events: auto;
  transform: translateY(0);
}

.main:focus {
  outline: none;
}

.sidebar {
  position: sticky;
  top: 0;
  flex: 0 0 var(--sidebar-w);
  width: var(--sidebar-w);
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
  padding: 18px 16px 16px;
  border-bottom: 1px solid var(--border-soft);
}

.brand__mark {
  display: inline-grid;
  place-items: center;
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  border-radius: var(--radius-sm);
  background: var(--primary);
  color: var(--on-primary);
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.brand__text {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.3;
}

.brand__text strong {
  font-size: 14.5px;
  font-weight: 650;
  letter-spacing: -0.01em;
  white-space: nowrap;
}

.brand__text small {
  margin-top: 2px;
  color: var(--text-faint);
  font-size: 11px;
  white-space: nowrap;
}

.nav {
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  flex: 1;
  padding: 14px 10px;
  gap: 2px;
}

.nav__item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 38px;
  padding: 0 10px;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  font-size: var(--fs-body);
  font-weight: 500;
  transition-property: background-color, color;
  transition-duration: var(--dur-fast);
  transition-timing-function: var(--ease);
}

.nav__item:hover {
  background: var(--surface-2);
  color: var(--text);
}

.nav__icon {
  flex: 0 0 16px;
  color: currentColor;
  opacity: 0.8;
}

.nav__item--active,
.nav__item--active:hover {
  background: var(--primary-soft);
  color: var(--text);
  font-weight: 600;
}

.nav__item--active .nav__icon {
  color: var(--text);
  opacity: 1;
}

.sidebar__foot {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px 14px 16px;
  border-top: 1px solid var(--border-soft);
}

.scanner-state {
  display: flex;
  align-items: center;
  gap: 7px;
  width: 100%;
  font-size: var(--fs-meta);
  color: var(--text-muted);
}

.scanner-state__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex: 0 0 auto;
}

.scanner-state--idle .scanner-state__dot {
  background: var(--text-faint);
}

.scanner-state--on .scanner-state__dot {
  background: var(--success);
  box-shadow: 0 0 0 0 color-mix(in srgb, var(--success) 55%, transparent);
  animation: breathe-ok 2.2s ease-out infinite;
}

.scanner-state--off .scanner-state__dot {
  background: var(--danger);
  box-shadow: 0 0 0 0 color-mix(in srgb, var(--danger) 55%, transparent);
  animation: breathe-bad 1.6s ease-out infinite;
}

.scanner-state--off .scanner-state__text {
  color: var(--danger);
}

.footer-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--border-soft);
  font-size: var(--fs-micro);
}

.footer-actions {
  margin-right: auto;
}

.footer-user__name {
  font-family: var(--font-mono);
  letter-spacing: 0.06em;
  color: var(--text-faint);
}

.footer-logout {
  padding: 0;
  border: 0;
  background: none;
  color: var(--text-muted);
  font: inherit;
  cursor: pointer;
}

.footer-logout:hover {
  color: var(--text);
  text-decoration: underline;
  text-underline-offset: 2px;
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

/* 懒加载路由首次进入时的占位，避免内容区出现空白闪烁 */
.route-fallback {
  max-width: var(--content-max);
  margin: 0 auto;
  padding: 32px 36px;
}

@media (max-width: 1023px) {
  .route-fallback {
    padding: 24px;
  }
}

@media (max-width: 767px) {
  .route-fallback {
    padding: var(--space-4);
  }
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
    gap: 8px;
    padding: 8px 16px 0;
    border-right: 0;
    border-bottom: 1px solid var(--border);
    background: color-mix(in srgb, var(--surface) 92%, transparent);
    backdrop-filter: blur(12px);
  }

  .brand {
    padding: 0;
    border-bottom: 0;
  }

  .brand__text small {
    display: none;
  }

  .nav {
    order: 3;
    flex: 0 0 100%;
    flex-direction: row;
    margin: 0;
    padding: 0;
    overflow-x: auto;
    overflow-y: hidden;
    gap: 0;
  }

  .nav__item {
    flex: 1 0 auto;
    justify-content: center;
    min-height: 42px;
    padding: 0 9px;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    font-size: 12.5px;
    white-space: nowrap;
  }

  .nav__item--active {
    background: none;
    border-bottom-color: var(--text);
  }

  .nav__icon {
    display: none;
  }

  .sidebar__foot {
    order: 2;
    margin-left: auto;
    flex-direction: row;
    align-items: center;
    gap: 10px;
    padding: 0;
    border-top: 0;
  }

  .scanner-state {
    width: auto;
  }

  .scanner-state__text {
    font-size: var(--fs-micro);
    white-space: nowrap;
  }

  .footer-row {
    padding-top: 0;
    border-top: 0;
  }

  .footer-user__name {
    display: none;
  }

  .footer-logout {
    white-space: nowrap;
  }
}

@media (prefers-reduced-motion: reduce) {
  .scanner-state__dot {
    animation: none !important;
  }
}
</style>
