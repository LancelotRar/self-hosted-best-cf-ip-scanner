import { createApp } from "vue";
import ElementPlus from "element-plus";
import zhCn from "element-plus/es/locale/lang/zh-cn";
import { createPinia } from "pinia";

import "element-plus/dist/index.css";
import "./styles.css";

import App from "./App.vue";
import { setUnauthorizedHandler } from "./api";
import router from "./router";
import { useAuthStore } from "./stores/auth";

const app = createApp(App);
const pinia = createPinia();

app.use(pinia);
app.use(router);
app.use(ElementPlus, { locale: zhCn });

// 任何接口返回 401 都回到登录页；由 main 统一接线，避免 api 反向依赖路由。
setUnauthorizedHandler(() => {
  const auth = useAuthStore(pinia);
  auth.markLoggedOut();
  void router.push({ name: "login" });
});

app.mount("#app");
