import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../api";
import { useConfigStore } from "../config";
import type { ConfigResponse, Param, SaveResult } from "../../types";

vi.mock("../../api", () => ({
  get: vi.fn(),
  put: vi.fn(),
  post: vi.fn(),
}));

const intParam: Param = {
  name: "MAX_CANDIDATES",
  group: "采样",
  kind: "int",
  label: "候选总量上限",
  help: "",
  default: 0,
  value: 0,
  source: "default",
  configured: false,
  secret: false,
  read_only: false,
  restart: false,
  consumer: "scanner",
  effect: "next_round",
};

const response: ConfigResponse = {
  hash: "hash-1",
  mtime: "2026-11-03T00:00:00Z",
  file_size: 20,
  params: [intParam],
};

const saveResult: SaveResult = {
  written: true,
  hash: "hash-2",
  changed: [{ name: "MAX_CANDIDATES", old: "0", new: "200", effect: "next_round" }],
  effects: { next_round: ["MAX_CANDIDATES"], schedule_reloaded: false, restart_required: [] },
  verification: { status: "verified", checked_at: "2026-11-03T00:00:00Z", details: [] },
  next_run: null,
  warnings: [],
};

async function loadedStore() {
  vi.mocked(api.get).mockResolvedValue(response as never);
  const store = useConfigStore();
  await store.load();
  return store;
}

describe("config store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it("load 建立服务端快照", async () => {
    const store = await loadedStore();
    expect(store.hash).toBe("hash-1");
    expect(store.dirty).toBe(false);
    expect(store.values.MAX_CANDIDATES).toBe(0);
  });

  it("keeps dirty edits when save fails", async () => {
    const store = await loadedStore();
    vi.mocked(api.put).mockRejectedValue(new Error("validation failed"));
    store.applyLocal({ MAX_CANDIDATES: 200 });
    await expect(store.save()).rejects.toThrow();
    expect(store.dirty).toBe(true);
    expect(store.values.MAX_CANDIDATES).toBe(200);
  });

  it("cancel restores the last server snapshot", async () => {
    const store = await loadedStore();
    store.applyLocal({ MAX_CANDIDATES: 200 });
    store.cancel();
    expect(store.dirty).toBe(false);
    expect(store.values.MAX_CANDIDATES).toBe(0);
  });

  it("save success clears dirty and stores the result panel data", async () => {
    const store = await loadedStore();
    vi.mocked(api.put).mockResolvedValue(saveResult as never);
    vi.mocked(api.get).mockResolvedValue({
      ...response,
      hash: "hash-2",
      params: [{ ...intParam, value: 200, configured: true, source: "dotenv" }],
    } as never);

    store.applyLocal({ MAX_CANDIDATES: 200 });
    await store.save();

    expect(api.put).toHaveBeenCalledWith("/api/config", {
      hash: "hash-1",
      values: { MAX_CANDIDATES: "200" },
    });
    expect(store.dirty).toBe(false);
    expect(store.lastResult?.verification.status).toBe("verified");
  });
});
