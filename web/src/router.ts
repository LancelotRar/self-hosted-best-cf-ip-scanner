import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";

import AppShell from "./layouts/AppShell.vue";
import ConfigView from "./views/ConfigView.vue";
import { useAuthStore } from "./stores/auth";
import LoginView from "./views/LoginView.vue";
import OverviewView from "./views/OverviewView.vue";
import PlaceholderView from "./views/PlaceholderView.vue";
import SetupView from "./views/SetupView.vue";

const routes: RouteRecordRaw[] = [
  { path: "/login", name: "login", component: LoginView },
  { path: "/setup", name: "setup", component: SetupView },
  {
    path: "/",
    component: AppShell,
    children: [
      { path: "", name: "overview", component: OverviewView, meta: { title: "总览" } },
      { path: "config", name: "config", component: ConfigView, meta: { title: "参数" } },
      { path: "schedule", name: "schedule", component: PlaceholderView, meta: { title: "调度" } },
      { path: "runs", name: "runs", component: PlaceholderView, meta: { title: "运行" } },
      { path: "logs", name: "logs", component: PlaceholderView, meta: { title: "日志" } },
      { path: "outputs", name: "outputs", component: PlaceholderView, meta: { title: "产物" } },
      { path: "library", name: "library", component: PlaceholderView, meta: { title: "IP 库" } },
      { path: "publish", name: "publish", component: PlaceholderView, meta: { title: "发布" } },
      { path: "system", name: "system", component: PlaceholderView, meta: { title: "系统" } },
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
