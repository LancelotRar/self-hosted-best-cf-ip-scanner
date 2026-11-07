import { expect, test } from "@playwright/test";

import { ensureSession } from "./helpers";

/** 保存按钮在底部操作栏（自定义 IP 库标签里也有保存，必须限定范围）。 */
function saveButton(page: import("@playwright/test").Page) {
  return page.locator(".actionbar").getByRole("button", { name: "保存", exact: true });
}

function cancelButton(page: import("@playwright/test").Page) {
  return page.locator(".actionbar").getByRole("button", { name: "取消" });
}

test("保存结果面板显示写入/核对/生效方式/下次执行", async ({ page }) => {
  await ensureSession(page);
  await page.goto("/config");

  const field = page.locator("#param-SAMPLE_STRIDE");
  const original = await field.inputValue();
  const next = original === "512" ? "256" : "512";
  await field.fill(next);
  await expect(page.getByText("未保存 1 项")).toBeVisible();

  await saveButton(page).click();
  await expect(page.getByText("保存结果")).toBeVisible();
  await expect(page.getByText(/已写入|无变化/)).toBeVisible();
  await expect(page.getByText(/已核对通过|当前无法核对|需重启扫描容器/)).toBeVisible();
  await expect(page.getByText("调度热重载")).toBeVisible();
  await expect(page.getByText("下次执行")).toBeVisible();

  // 还原，避免污染测试栈的 .env
  await field.fill(original);
  await saveButton(page).click();
  await expect(page.getByText("没有未保存的修改")).toBeVisible();
});

test("取消恢复服务端快照", async ({ page }) => {
  await ensureSession(page);
  await page.goto("/config");

  const field = page.locator("#param-SAMPLE_STRIDE");
  const original = await field.inputValue();
  const next = original === "1024" ? "512" : "1024";
  await field.fill(next);
  await expect(page.getByText("未保存 1 项")).toBeVisible();

  await cancelButton(page).click();
  await expect(field).toHaveValue(original);
  await expect(page.getByText("没有未保存的修改")).toBeVisible();
});

test("数字控件把越界值夹到范围内", async ({ page }) => {
  await ensureSession(page);
  await page.goto("/config");

  const field = page.locator("#param-TCP_MIN_SUCCESS");
  const original = await field.inputValue();
  const atMax = original === "10";
  await field.fill("99");
  await field.press("Tab");

  // 失焦后控件把越界值夹到 max=10；本来就在上限时不再产生改动
  await expect(field).toHaveValue("10");
  if (atMax) {
    await expect(page.getByText("没有未保存的修改")).toBeVisible();
  } else {
    await expect(page.getByText("未保存 1 项")).toBeVisible();
    await cancelButton(page).click();
    await expect(field).toHaveValue(original);
  }
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

    const fieldA = pageA.locator("#param-SAMPLE_STRIDE");
    const original = await fieldA.inputValue();
    const first = original === "512" ? "1024" : "512";
    const second = original === "2048" ? "4096" : "2048";

    await fieldA.fill(first);
    await pageB.locator("#param-SAMPLE_STRIDE").fill(second);

    await saveButton(pageA).click();
    await expect(pageA.getByText("保存结果")).toBeVisible();

    await saveButton(pageB).click();
    await expect(pageB.getByText("文件已被修改")).toBeVisible();
  } finally {
    await contextA.close();
    await contextB.close();
  }
});
