import { createApp } from "vue";
import { createPinia } from "pinia";

// 先加载组件库基础样式，再加载项目样式；顺序决定 --el-* 桥接是否生效。
import "element-plus/dist/index.css";
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

// 等首个路由（含登录校验）就绪后再挂载：期间保留 index.html 的静态启动占位，
// 避免跨网访问时出现整页空白。
router
  .isReady()
  .catch(() => {
    /* 导航失败时仍然挂载，由页面自身展示错误 */
  })
  .then(() => app.mount("#app"));
