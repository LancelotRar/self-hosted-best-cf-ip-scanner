import { mount } from "@vue/test-utils";
import ElementPlus from "element-plus";
import { describe, expect, it } from "vitest";

import ParamField from "../ParamField.vue";
import type { Param } from "../../types";

const intParam: Param = {
  name: "SAMPLE_STRIDE",
  group: "采样",
  kind: "int",
  label: "采样步长",
  help: "每 N 个地址抽 1 个",
  default: 256,
  value: 256,
  source: "default",
  configured: false,
  secret: false,
  read_only: false,
  restart: false,
  consumer: "scanner",
  effect: "next_round",
  hidden: false,
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
      props: { param: intParam, modelValue: 256 },
      global: { plugins: [ElementPlus] },
    });
    expect(wrapper.find(".el-input-number").exists()).toBe(true);
    const input = wrapper.find(".el-input-number input");
    await input.setValue("512");
    await input.trigger("change");
    expect(wrapper.emitted("update:modelValue")?.[0]).toEqual([512]);
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

  it("参数说明作为可见帮助文字，并关联到控件", async () => {
    const wrapper = mount(ParamField, {
      props: { param: intParam, modelValue: 256 },
      global: { plugins: [ElementPlus] },
    });
    await wrapper.vm.$nextTick();
    const help = wrapper.find(".field__help");
    expect(help.text()).toContain("每 N 个地址抽 1 个");
    expect(wrapper.find(".el-input-number input").attributes("aria-describedby")).toBe(
      "param-SAMPLE_STRIDE-hint",
    );
  });

  it("hideHelp 收起分组内重复的字段说明", async () => {
    const wrapper = mount(ParamField, {
      props: { param: intParam, modelValue: 256, hideHelp: true },
      global: { plugins: [ElementPlus] },
    });
    await wrapper.vm.$nextTick();
    expect(wrapper.find(".field__help").exists()).toBe(false);
    expect(wrapper.find(".el-input-number input").attributes("aria-describedby")).toBeUndefined();
  });

  it("按内容类型分配表单栅格跨度", () => {
    const cases = [
      { param: intParam, modelValue: 256, span: "field--span-3" },
      { param: portParam, modelValue: [443], span: "field--span-6" },
      { param: boolParam, modelValue: false, span: "field--span-12" },
      { param: tzParam, modelValue: "Asia/Shanghai", span: "field--span-6" },
    ];

    for (const item of cases) {
      const wrapper = mount(ParamField, {
        props: { param: item.param, modelValue: item.modelValue },
        global: { plugins: [ElementPlus] },
      });
      expect(wrapper.classes()).toContain(item.span);
    }
  });

  it("错误显示在控件下方，并标记 aria-invalid", async () => {
    const wrapper = mount(ParamField, {
      props: { param: intParam, modelValue: 256, error: "不能超过 65536" },
      global: { plugins: [ElementPlus] },
    });
    await wrapper.vm.$nextTick();

    const input = wrapper.find(".el-input-number input");
    expect(wrapper.find(".field__error").text()).toBe("不能超过 65536");
    expect(input.attributes("aria-invalid")).toBe("true");
    expect(input.attributes("aria-describedby")).toBe("param-SAMPLE_STRIDE-error");
  });
});
