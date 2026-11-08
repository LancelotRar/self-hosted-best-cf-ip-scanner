import { createApp } from "vue";
import { createPinia } from "pinia";

import "./styles.css";

import App from "./App.vue";
import { setUnauthorizedHandler } from "./api";
import { initTheme } from "./composables/useTheme";
import { initUiSettings } from "./composables/useUiSettings";
import router from "./router";
import { useAuthStore } from "./stores/auth";

initTheme();
initUiSettings();

const app = createApp(App);
const pinia = createPinia();

app.use(pinia);
app.use(router);

// 任何接口返回 401 都回到登录页；由 main 统一接线，避免 api 反向依赖路由。
setUnauthorizedHandler(() => {
  const auth = useAuthStore(pinia);
  auth.markLoggedOut();
  void router.push({ name: "login" });
});

app.mount("#app");
