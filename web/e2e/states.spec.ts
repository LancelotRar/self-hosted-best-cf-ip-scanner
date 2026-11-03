import { expect, test } from "@playwright/test";

import { ensureSession } from "./helpers";

test("日志页显示连接状态与最后接收时间", async ({ page }) => {
  await ensureSession(page);
  await page.goto("/logs");
  await expect(page.getByText(/实时|连接中|已断开/).first()).toBeVisible();
  await expect(page.getByText(/最后接收/)).toBeVisible();
});

test("空产物显示尚无产物", async ({ page }) => {
  await ensureSession(page);
  await page.goto("/outputs");
  await expect(page.getByText("尚无产物（下一轮扫描成功后生成）")).toBeVisible();
  await expect(page.getByText(/本次读取/)).toBeVisible();
});

test("IP 库非法行显示行号", async ({ page }) => {
  await ensureSession(page);
  await page.goto("/library");
  await page.locator("textarea").fill("not-an-ip\n");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByText("存在无法解析的行，未保存")).toBeVisible();
  await expect(page.getByText(/第 1 行/)).toBeVisible();
});

test("发布无记录显示尚无发布记录", async ({ page }) => {
  await ensureSession(page);
  await page.goto("/publish");
  await page.getByRole("tab", { name: "最近结果" }).click();
  await expect(page.getByText("尚无发布记录（完成一轮扫描后生成）")).toBeVisible();
});
