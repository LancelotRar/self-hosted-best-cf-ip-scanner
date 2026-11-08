import { flushPromises, mount } from "@vue/test-utils";
import ElementPlus from "element-plus";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ConfigLocationsTab from "../ConfigLocationsTab.vue";
import * as api from "../../api";

vi.mock("../../api", () => ({
  get: vi.fn(),
  put: vi.fn(),
  post: vi.fn(),
  ApiError: class ApiError extends Error {},
}));

vi.mock("vue-router", () => ({ onBeforeRouteLeave: vi.fn() }));

const document = {
  hash: "hash-1",
  mtime: null,
  count: 2,
  entries: [
    { code: "HKG", country: "HK" },
    { code: "NRT", country: "JP" },
  ],
  read_at: "2026-11-08T00:00:00Z",
};

async function mounted() {
  vi.mocked(api.get).mockResolvedValue(document as never);
  const wrapper = mount(ConfigLocationsTab, {
    global: { plugins: [ElementPlus] },
  });
  await flushPromises();
  return wrapper;
}

function saveButton(wrapper: Awaited<ReturnType<typeof mounted>>) {
  return wrapper.findAll("button").find((button) => button.text().includes("保存"));
}

describe("ConfigLocationsTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("按数据库内容渲染条目，并提示非必要无需编辑", async () => {
    const wrapper = await mounted();
    const codes = wrapper
      .findAll(".loc-row__code input")
      .map((input) => (input.element as HTMLInputElement).value);
    expect(codes).toEqual(["HKG", "NRT"]);
    expect(wrapper.text()).toContain("非必要无需编辑");
    expect(saveButton(wrapper)?.attributes("disabled")).toBeDefined();
  });

  it("新增空行后视为不合法，保存被禁用", async () => {
    const wrapper = await mounted();
    const add = wrapper.findAll("button").find((button) => button.text().includes("新增一行"));
    await add!.trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("有不合法的条目");
    expect(saveButton(wrapper)?.attributes("disabled")).toBeDefined();
  });

  it("重复的机房代码会被就地标出", async () => {
    const wrapper = await mounted();
    const add = wrapper.findAll("button").find((button) => button.text().includes("新增一行"));
    await add!.trigger("click");
    await flushPromises();

    const inputs = wrapper.findAll(".loc-row__code input");
    await inputs[inputs.length - 1].setValue("HKG");
    await flushPromises();

    expect(wrapper.text()).toContain("重复");
  });
});
