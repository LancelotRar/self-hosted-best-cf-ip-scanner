import { expect, test } from "@playwright/test";

import { ensureSession } from "./helpers";

test("日志页显示连接状态与最后接收时间", async ({ page }) => {
  await ensureSession(page);
  await page.goto("/logs");
  await expect(page.getByText(/实时|连接中|已断开/).first()).toBeVisible();
  await expect(page.getByText(/最后接收/)).toBeVisible();
});

test("总览展示六个只读区块", async ({ page }) => {
  await ensureSession(page);

  for (const title of [
    "容器状态",
    "IP 库信息",
    "计划详情",
    "近期扫描情况",
    "产物情况",
    "推送情况",
  ]) {
    await expect(page.getByText(title, { exact: true }).first()).toBeVisible();
  }
});

test("页头只有标题与备注，没有按钮或图标", async ({ page }) => {
  await ensureSession(page);

  await expect(page.getByRole("heading", { name: "总览" })).toBeVisible();
  await expect(page.getByText("扫描器、IP 库、计划、运行、产物与推送情况的综合视图")).toBeVisible();
  await expect(page.locator(".page-head button")).toHaveCount(0);
  await expect(page.locator(".page-head .page-head__icon")).toHaveCount(0);
});

test("旧链接重定向：产物 / IP 库 / 发布 回到总览", async ({ page }) => {
  await ensureSession(page);

  for (const path of ["/outputs", "/library", "/publish"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: "总览" })).toBeVisible();
    await expect(page).toHaveURL(/\/$/);
  }
});

test("主导航固定五项且只高亮当前页", async ({ page }) => {
  await ensureSession(page);

  const items = page.locator(".nav__item");
  await expect(items).toHaveCount(5);
  await expect(page.locator(".nav__item--active")).toHaveCount(1);
  await expect(page.locator(".nav__item--active")).toHaveText("总览");
});
