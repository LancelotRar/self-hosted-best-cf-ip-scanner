import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";
import Components from "unplugin-vue-components/vite";
import { ElementPlusResolver } from "unplugin-vue-components/resolvers";

export default defineConfig({
  base: "/",
  plugins: [
    vue(),
    Components({
      // 样式由 main.ts 显式引入：保证 Element Plus 基础样式先于项目样式加载，
      // 否则按需注入的样式会覆盖设计 token（主色、圆角、控件高度全部失效）。
      resolvers: [ElementPlusResolver({ importStyle: false })],
      dts: false,
    }),
  ],
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8080",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.spec.ts"],
    server: {
      deps: {
        inline: ["element-plus"],
      },
    },
  },
});
