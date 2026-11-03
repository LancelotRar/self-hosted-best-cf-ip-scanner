import { expect, type Page } from "@playwright/test";

export const PASSWORD = process.env.E2E_PASSWORD ?? "e2e-correct-horse";

/** 首次访问走设置流程，已初始化则登录；结束时停在总览页。 */
export async function ensureSession(page: Page): Promise<void> {
  await page.goto("/");

  const setupHeading = page.getByRole("heading", { name: "首次设置" });
  const loginHeading = page.getByRole("heading", { name: "登录", exact: true });

  // SPA 首屏渲染有延迟：先等到「设置 / 登录 / 已登录」三者之一出现，再决定走哪条路。
  await expect(
    setupHeading.or(loginHeading).or(page.locator(".nav__item").first()),
  ).toBeVisible();

  if (await setupHeading.isVisible()) {
    await page.getByPlaceholder("至少 8 个字符").fill(PASSWORD);
    await page.getByPlaceholder("再输入一次").fill(PASSWORD);
    await page.getByRole("button", { name: "设置并登录" }).click();
    await expect(page.getByRole("heading", { name: "信息总览" })).toBeVisible();
    return;
  }

  if (await loginHeading.isVisible()) {
    await page.getByLabel("管理员密码").fill(PASSWORD);
    await page.getByRole("button", { name: "登录" }).click();
  }
  await expect(page.getByRole("heading", { name: "信息总览" })).toBeVisible();
}

/** 退出登录：新布局把退出按钮放在侧栏底部。 */
export async function logout(page: Page): Promise<void> {
  await page.locator(".footer-logout").click();
  await expect(page.getByRole("heading", { name: "登录", exact: true })).toBeVisible();
}
