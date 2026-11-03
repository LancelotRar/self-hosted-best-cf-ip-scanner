import { expect, test } from "@playwright/test";

import { ensureSession } from "./helpers";

test("日志页显示连接状态与最后接收时间", async ({ page }) => {
  await ensureSession(page);
  await page.goto("/logs");
  await expect(page.getByText(/实时|连接中|已断开/).first()).toBeVisible();
  await expect(page.getByText(/最后接收/)).toBeVisible();
});

test("日志每行都是 [时间戳][等级]：消息", async ({ page }) => {
  await ensureSession(page);
  await page.goto("/logs");

  const body = page.locator(".console__body");
  await expect(body).toBeVisible();
  await expect(body).toContainText(/\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]\[(信息|警告|错误)\]：/);
});

test("信息总览展示六个只读区块", async ({ page }) => {
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

  await expect(page.getByRole("heading", { name: "信息总览" })).toBeVisible();
  await expect(page.getByText("扫描器、IP 库、计划、运行、产物与推送情况的综合视图")).toBeVisible();
  await expect(page.locator(".page-head button")).toHaveCount(0);
  await expect(page.locator(".page-head .page-head__icon")).toHaveCount(0);
});

test("旧链接重定向：产物 / IP 库 / 发布 回到总览", async ({ page }) => {
  await ensureSession(page);

  for (const path of ["/outputs", "/library", "/publish"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: "信息总览" })).toBeVisible();
    await expect(page).toHaveURL(/\/$/);
  }
});

test("主导航固定五项且只高亮当前页", async ({ page }) => {
  await ensureSession(page);

  const items = page.locator(".nav__item");
  await expect(items).toHaveCount(5);
  await expect(items).toHaveText(["信息总览", "参数调整", "手动运行", "查看日志", "设置"]);
  await expect(page.locator(".nav__item--active")).toHaveCount(1);
  await expect(page.locator(".nav__item--active")).toHaveText("信息总览");
});

test("参数调整页有「自定义 IP 库」说明与编辑框", async ({ page }) => {
  await ensureSession(page);
  await page.goto("/config");

  await page.getByRole("tab", { name: "自定义 IP 库" }).click();
  await expect(page.getByText("格式说明")).toBeVisible();
  await expect(page.locator(".library-editor__input textarea")).toBeVisible();
  await expect(page.getByText(/保存会覆盖数据目录下的地址库文件/)).toBeVisible();
});

test("IP 库非法行给出行号且不写入文件", async ({ page }) => {
  await ensureSession(page);
  await page.goto("/config");
  await page.getByRole("tab", { name: "自定义 IP 库" }).click();

  const actions = page.locator(".library-editor__actions");
  const editor = page.locator(".library-editor__input textarea");
  await expect(editor).toBeVisible();
  await editor.fill("not-an-ip\n");
  await actions.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByText("第 1 行")).toBeVisible();

  await actions.getByRole("button", { name: "还原" }).click();
  await expect(actions.getByText("没有未保存的修改")).toBeVisible();
});

test("表格列宽拖动后写入 localStorage", async ({ page }) => {
  await ensureSession(page);

  const table = page.locator(".scroll-table").last();
  await table.scrollIntoViewIfNeeded();
  const box = await table.locator(".el-table__header th").nth(1).boundingBox();
  if (!box) throw new Error("未找到表头");
  const x = box.x + box.width - 4;
  const y = box.y + box.height / 2;

  await page.mouse.move(x, y);
  await page.mouse.move(x - 1, y);
  await page.mouse.down();
  await page.mouse.move(x + 60, y, { steps: 8 });
  await page.mouse.up();

  const stored = await page.evaluate(() => localStorage.getItem("panel-table-widths"));
  expect(stored).toContain("overview-outputs");
});

test("未保存离开弹窗提供继续编辑 / 放弃修改 / 保存并离开", async ({ page }) => {
  await ensureSession(page);
  await page.goto("/config");

  const field = page.locator("#param-MAX_CANDIDATES");
  const original = await field.inputValue();
  await field.fill(original === "200" ? "201" : "200");

  await page.locator(".nav__item").filter({ hasText: "查看日志" }).click();
  const dialog = page.locator(".el-dialog").filter({ hasText: "未保存的修改" });
  await expect(dialog.getByRole("button", { name: "继续编辑" })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "放弃修改" })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "保存并离开" })).toBeVisible();

  await dialog.getByRole("button", { name: "放弃修改" }).click();
  await expect(page).toHaveURL(/\/logs/);
});
