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

const tzParam: Param = {
  ...intParam,
  name: "TZ",
  kind: "str",
  label: "时区",
  default: "Asia/Shanghai",
  value: "Asia/Shanghai",
};

const cronParam: Param = {
  ...intParam,
  name: "CRON_SCHEDULE",
  kind: "cron",
  label: "调度表达式",
  default: "30 */6 * * *",
  value: "30 */6 * * *",
};

describe("ParamField", () => {
  it("int 参数使用数字步进器", async () => {
    const wrapper = mount(ParamField, {
      props: { param: intParam, modelValue: 1 },
      global: { plugins: [ElementPlus] },
    });
    expect(wrapper.find(".el-input-number").exists()).toBe(true);
    const input = wrapper.find(".el-input-number input");
    await input.setValue("200");
    await input.trigger("change");
    expect(wrapper.emitted("update:modelValue")?.[0]).toEqual([200]);
  });

  it("端口参数使用多选，已选端口以标签展示", () => {
    const wrapper = mount(ParamField, {
      props: { param: portParam, modelValue: [443] },
      global: { plugins: [ElementPlus] },
    });
    expect(wrapper.find(".el-select").exists()).toBe(true);
    expect(wrapper.text()).toContain("443");
  });

  it("布尔参数使用开关", async () => {
    const wrapper = mount(ParamField, {
      props: { param: boolParam, modelValue: false },
      global: { plugins: [ElementPlus] },
    });
    const switchInput = wrapper.find("[role='switch'], input[type='checkbox']");
    await switchInput.trigger("click");
    expect(wrapper.emitted("update:modelValue")?.[0]).toEqual([true]);
  });

  it("时区参数使用可搜索下拉", () => {
    const wrapper = mount(ParamField, {
      props: { param: tzParam, modelValue: "Asia/Shanghai" },
      global: { plugins: [ElementPlus] },
    });
    expect(wrapper.find(".el-select").exists()).toBe(true);
    expect(wrapper.text()).toContain("Asia/Shanghai");
  });

  it("cron 参数提供常用模板菜单", () => {
    const wrapper = mount(ParamField, {
      props: { param: cronParam, modelValue: "30 */6 * * *" },
      global: { plugins: [ElementPlus] },
    });
    expect(wrapper.text()).toContain("常用模板");
    expect(wrapper.find(".el-input").exists()).toBe(true);
  });
});
