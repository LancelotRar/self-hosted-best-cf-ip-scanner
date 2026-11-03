import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  fullyParallel: false,
  retries: 1,
  timeout: 45_000,
  // 保存参数会写 .env 并核对扫描容器，冷启动时可能超过 5s，统一放宽断言等待。
  expect: { timeout: 15_000 },
  reporter: [["list"]],
  use: {
    baseURL: process.env.PANEL_URL ?? "http://127.0.0.1:8080",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
});
