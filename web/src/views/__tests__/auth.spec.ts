import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../api";
import { useAuthStore } from "../../stores/auth";
import type { AuthStatus } from "../../types";

vi.mock("../../api", () => ({
  get: vi.fn(),
  post: vi.fn(),
}));

const status = (overrides: Partial<AuthStatus> = {}): AuthStatus => ({
  initialized: true,
  authenticated: false,
  username: "admin",
  ...overrides,
});

describe("auth store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it("初始状态未就绪且需要设置", () => {
    const store = useAuthStore();
    expect(store.ready).toBe(false);
    expect(store.needsSetup).toBe(true);
  });

  it("refresh 写入服务端状态", async () => {
    vi.mocked(api.get).mockResolvedValue(status() as never);
    const store = useAuthStore();
    await store.refresh();
    expect(store.ready).toBe(true);
    expect(store.initialized).toBe(true);
    expect(store.authenticated).toBe(false);
  });

  it("login 成功后标记已登录", async () => {
    vi.mocked(api.post).mockResolvedValue({ authenticated: true, username: "admin" });
    vi.mocked(api.get).mockResolvedValue(status({ authenticated: true }) as never);
    const store = useAuthStore();
    await store.login("correct horse");
    expect(store.authenticated).toBe(true);
    expect(api.post).toHaveBeenCalledWith("/api/auth/login", { password: "correct horse" });
  });

  it("login 失败保留未登录并抛错", async () => {
    vi.mocked(api.post).mockRejectedValue(new Error("密码错误"));
    const store = useAuthStore();
    await expect(store.login("wrong")).rejects.toThrow("密码错误");
    expect(store.authenticated).toBe(false);
    expect(store.loading).toBe(false);
  });
});
