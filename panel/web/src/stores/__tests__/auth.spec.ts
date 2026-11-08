import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../api";
import { useAuthStore } from "../auth";

vi.mock("../../api", () => ({
  get: vi.fn(),
  put: vi.fn(),
  post: vi.fn(),
}));

describe("auth store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it("records whether setup requires a token", () => {
    const store = useAuthStore();
    store.apply({
      initialized: false,
      authenticated: false,
      username: null,
      setup_token_required: true,
    });
    expect(store.setupTokenRequired).toBe(true);
  });

  it("sends X-Setup-Token when a token is provided", async () => {
    vi.mocked(api.post).mockResolvedValue({} as never);
    vi.mocked(api.get).mockResolvedValue({
      initialized: true,
      authenticated: true,
      username: "admin",
    } as never);

    const store = useAuthStore();
    await store.setup("password", "setup-secret");

    expect(api.post).toHaveBeenCalledWith(
      "/api/auth/setup",
      { password: "password" },
      { "X-Setup-Token": "setup-secret" },
    );
  });
});
