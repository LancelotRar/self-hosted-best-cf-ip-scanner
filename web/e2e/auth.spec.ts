import { expect, test } from "@playwright/test";

import { PASSWORD } from "./helpers";

test("首次设置 → 登录 → 错误密码提示", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "首次设置" })).toBeVisible();

  await page.getByPlaceholder("至少 8 个字符").fill(PASSWORD);
  await page.getByPlaceholder("再输入一次").fill(PASSWORD);
  await page.getByRole("button", { name: "设置并登录" }).click();
  await expect(page.getByRole("heading", { name: "总览" })).toBeVisible();

  await page.getByRole("button", { name: /admin/ }).click();
  await page.getByText("退出登录").click();
  await expect(page.getByRole("heading", { name: "登录运维面板" })).toBeVisible();

  await page.getByPlaceholder("管理员密码").fill("definitely-wrong");
  await page.getByRole("button", { name: "登录" }).click();
  await expect(page.getByText("用户名或密码错误")).toBeVisible();

  await page.getByPlaceholder("管理员密码").fill(PASSWORD);
  await page.getByRole("button", { name: "登录" }).click();
  await expect(page.getByRole("heading", { name: "总览" })).toBeVisible();
});
