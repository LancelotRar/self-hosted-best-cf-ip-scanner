import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";

import AppShell from "./layouts/AppShell.vue";
import { useAuthStore } from "./stores/auth";

// 页面级懒加载：首屏只加载 AppShell 与当前路由，其余页面按需下载。
const OverviewView = () => import("./views/OverviewView.vue");
const ConfigView = () => import("./views/ConfigView.vue");
const RunsView = () => import("./views/RunsView.vue");
const LogsView = () => import("./views/LogsView.vue");
const SettingsView = () => import("./views/SettingsView.vue");
const LoginView = () => import("./views/LoginView.vue");
const SetupView = () => import("./views/SetupView.vue");

const routes: RouteRecordRaw[] = [
  { path: "/login", name: "login", component: LoginView },
  { path: "/setup", name: "setup", component: SetupView },
  {
    path: "/",
    component: AppShell,
    children: [
      { path: "", name: "overview", component: OverviewView, meta: { title: "总览" } },
      { path: "config", name: "config", component: ConfigView, meta: { title: "参数" } },
      { path: "schedule", redirect: { name: "config", query: { tab: "schedule" } } },
      { path: "runs", name: "runs", component: RunsView, meta: { title: "运行" } },
      { path: "logs", name: "logs", component: LogsView, meta: { title: "日志" } },
      { path: "outputs", redirect: { name: "overview" } },
      { path: "library", redirect: { name: "overview" } },
      { path: "publish", redirect: { name: "overview" } },
      { path: "system", redirect: { name: "settings" } },
      { path: "settings", name: "settings", component: SettingsView, meta: { title: "设置" } },
    ],
  },
  { path: "/:pathMatch(.*)*", redirect: "/" },
];

export const router = createRouter({
  history: createWebHistory("/"),
  routes,
  scrollBehavior: () => ({ top: 0 }),
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (!auth.ready) {
    try {
      await auth.refresh();
    } catch {
      // 服务端不可达时让页面显示错误，而不是死循环跳转
      return to.name === "login" ? true : { name: "login" };
    }
  }
  if (!auth.initialized) {
    return to.name === "setup" ? true : { name: "setup" };
  }
  if (!auth.authenticated) {
    return to.name === "login" ? true : { name: "login" };
  }
  if (to.name === "login" || to.name === "setup") {
    return { name: "overview" };
  }
  return true;
});

export default router;
