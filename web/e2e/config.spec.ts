import { expect, test } from "@playwright/test";

import { ensureSession } from "./helpers";

test("保存结果面板显示写入/核对/生效方式/下次执行", async ({ page }) => {
  await ensureSession(page);
  await page.goto("/config");

  const field = page.locator("#param-MAX_CANDIDATES");
  await field.fill("200");
  await expect(page.getByText("未保存 1 项")).toBeVisible();

  await page.locator(".actionbar").getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByText("保存结果")).toBeVisible();
  await expect(page.getByText("已写入")).toBeVisible();
  await expect(page.getByText("核对状态")).toBeVisible();
  await expect(page.getByText("生效方式")).toBeVisible();
  await expect(page.getByText("下次执行")).toBeVisible();
});

test("取消恢复服务端快照", async ({ page }) => {
  await ensureSession(page);
  await page.goto("/config");

  const field = page.locator("#param-MAX_CANDIDATES");
  const original = await field.inputValue();
  await field.fill("123");
  await expect(page.getByText("未保存 1 项")).toBeVisible();

  await page.locator(".actionbar").getByRole("button", { name: "取消" }).click();
  await expect(field).toHaveValue(original);
  await expect(page.getByText("没有未保存的修改")).toBeVisible();
});

test("非法值保存失败并保留输入", async ({ page }) => {
  await ensureSession(page);
  await page.goto("/config");

  const field = page.locator("#param-TCP_MIN_SUCCESS");
  const original = await field.inputValue();
  await field.fill("99");
  await page.locator(".actionbar").getByRole("button", { name: "保存", exact: true }).click();

  await expect(page.getByText(/TCP_MIN_SUCCESS/)).toBeVisible();
  await expect(field).toHaveValue("99");
  await expect(page.getByText("未保存 1 项")).toBeVisible();

  await page.locator(".actionbar").getByRole("button", { name: "取消" }).click();
  await expect(field).toHaveValue(original);
});

test("两个窗口同时保存时提示文件已被修改", async ({ browser }) => {
  const contextA = await browser.newContext();
  const contextB = await browser.newContext();
  const pageA = await contextA.newPage();
  const pageB = await contextB.newPage();

  try {
    await ensureSession(pageA);
    await ensureSession(pageB);
    await pageA.goto("/config");
    await pageB.goto("/config");

    await pageA.locator("#param-MAX_CANDIDATES").fill("300");
    await pageB.locator("#param-MAX_CANDIDATES").fill("400");

    await pageA.locator(".actionbar").getByRole("button", { name: "保存", exact: true }).click();
    await expect(pageA.getByText("保存结果")).toBeVisible();

    await pageB.locator(".actionbar").getByRole("button", { name: "保存", exact: true }).click();
    await expect(pageB.getByText("文件已被修改")).toBeVisible();
  } finally {
    await contextA.close();
    await contextB.close();
  }
});
