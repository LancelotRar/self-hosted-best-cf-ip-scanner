import { mount } from "@vue/test-utils";
import ElementPlus from "element-plus";
import { describe, expect, it } from "vitest";

import ParamField from "../ParamField.vue";
import type { Param } from "../../types";

const intParam: Param = {
  name: "MAX_CANDIDATES",
  group: "采样",
  kind: "int",
  label: "候选总量上限",
  help: "0 = 不限",
  default: 0,
  value: 1,
  source: "default",
  configured: false,
  secret: false,
  read_only: false,
  restart: false,
  consumer: "scanner",
  effect: "next_round",
};

const portParam: Param = {
  ...intParam,
  name: "PROBE_PORTS",
  kind: "ports",
  label: "候选端口集",
  default: [443],
  value: [443],
};

const boolParam: Param = {
  ...intParam,
  name: "COUNTRY_FILTERS",
  kind: "bool",
  label: "生成国家列表",
  default: false,
  value: false,
};

describe("ParamField", () => {
  it("emits numeric value for int param", async () => {
    const wrapper = mount(ParamField, {
      props: { param: intParam, modelValue: 1 },
      global: { plugins: [ElementPlus] },
    });
    await wrapper.find("input").setValue("200");
    expect(wrapper.emitted("update:modelValue")?.[0]).toEqual([200]);
  });

  it("splits ports input into numbers", async () => {
    const wrapper = mount(ParamField, {
      props: { param: portParam, modelValue: [443] },
      global: { plugins: [ElementPlus] },
    });
    await wrapper.find("input").setValue("443, 2053");
    expect(wrapper.emitted("update:modelValue")?.[0]).toEqual([[443, 2053]]);
  });

  it("emits boolean for switch", async () => {
    const wrapper = mount(ParamField, {
      props: { param: boolParam, modelValue: false },
      global: { plugins: [ElementPlus] },
    });
    const switchInput = wrapper.find("[role='switch'], input[type='checkbox']");
    await switchInput.trigger("click");
    expect(wrapper.emitted("update:modelValue")?.[0]).toEqual([true]);
  });
});
