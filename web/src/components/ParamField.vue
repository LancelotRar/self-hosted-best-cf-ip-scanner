<script setup lang="ts">
import { computed } from "vue";

import type { Param } from "../types";

const props = defineProps<{
  param: Param;
  modelValue: unknown;
  disabled?: boolean;
}>();

const emit = defineEmits<{ "update:modelValue": [value: unknown] }>();

const disabled = computed(() => props.disabled || props.param.read_only);

const textValue = computed(() => {
  const value = props.modelValue;
  if (Array.isArray(value)) return value.join(",");
  if (value === null || value === undefined) return "";
  return String(value);
});

const defaultText = computed(() => {
  const value = props.param.default;
  if (Array.isArray(value)) return value.join(",");
  if (typeof value === "boolean") return value ? "true" : "false";
  return String(value);
});

const effectTag = computed(() => {
  switch (props.param.effect) {
    case "restart_required":
      return { label: "需重启", tone: "warning" };
    case "schedule_reload":
      return { label: "热重载", tone: "info" };
    default:
      return { label: "下一轮", tone: "success" };
  }
});

function onText(value: string) {
  emit("update:modelValue", value);
}

function onNumber(value: string) {
  if (value === "") {
    emit("update:modelValue", 0);
    return;
  }
  const parsed = props.param.kind === "int" ? Number.parseInt(value, 10) : Number(value);
  emit("update:modelValue", Number.isNaN(parsed) ? 0 : parsed);
}

function onList(value: string) {
  const items = value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => Number(item))
    .filter((item) => !Number.isNaN(item));
  emit("update:modelValue", items);
}

function onBool(value: string | number | boolean) {
  emit("update:modelValue", Boolean(value));
}
</script>

<template>
  <div class="field" :class="{ 'field--readonly': disabled }">
    <div class="field__head">
      <label class="field__label" :for="`param-${param.name}`">{{ param.label }}</label>
      <div class="field__tags">
        <span class="tag" :class="`tag--${effectTag.tone}`">{{ effectTag.label }}</span>
        <span class="tag">{{ param.source === "dotenv" ? "来自 .env" : "默认值" }}</span>
        <span v-if="param.read_only" class="tag">只读</span>
        <span v-else-if="param.secret" class="tag">
          {{ param.configured ? "已配置" : "未配置" }}
        </span>
      </div>
    </div>

    <el-switch
      v-if="param.kind === 'bool'"
      :model-value="Boolean(modelValue)"
      :disabled="disabled"
      @change="onBool"
    />
    <el-input
      v-else-if="param.kind === 'int' || param.kind === 'float'"
      :id="`param-${param.name}`"
      type="number"
      :model-value="textValue"
      :disabled="disabled"
      :aria-describedby="`param-${param.name}-help`"
      @input="onNumber"
    />
    <el-input
      v-else-if="param.kind === 'ports' || param.kind === 'csv_int'"
      :id="`param-${param.name}`"
      class="mono"
      :model-value="textValue"
      :disabled="disabled"
      placeholder="逗号分隔，例如 443,2053"
      :aria-describedby="`param-${param.name}-help`"
      @input="onList"
    />
    <el-input
      v-else-if="param.secret"
      :id="`param-${param.name}`"
      type="password"
      show-password
      :model-value="textValue"
      :disabled="disabled"
      :placeholder="param.configured ? '已配置；留空表示不修改' : '未配置'"
      :aria-describedby="`param-${param.name}-help`"
      @input="onText"
    />
    <el-input
      v-else
      :id="`param-${param.name}`"
      :class="{ mono: param.kind === 'cron' || param.kind === 'path' }"
      :model-value="textValue"
      :disabled="disabled"
      :aria-describedby="`param-${param.name}-help`"
      @input="onText"
    />

    <p :id="`param-${param.name}-help`" class="field__help">{{ param.help }}</p>
    <p class="field__default">默认：{{ defaultText }}</p>
  </div>
</template>

<style scoped>
.field {
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--border);
}

.field:last-child {
  border-bottom: none;
}

.field--readonly {
  opacity: 0.82;
}

.field__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
  flex-wrap: wrap;
}

.field__label {
  font-weight: 600;
  font-size: 13px;
}

.field__tags {
  display: flex;
  gap: var(--space-1);
  flex-wrap: wrap;
}

.tag {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 6px;
  border-radius: 4px;
  border: 1px solid var(--border);
  background: var(--surface-2);
  color: var(--text-muted);
  font-size: 11px;
  line-height: 1;
  white-space: nowrap;
}

.tag--success {
  color: var(--success);
  border-color: color-mix(in srgb, var(--success) 38%, var(--border));
}

.tag--warning {
  color: var(--warning);
  border-color: color-mix(in srgb, var(--warning) 38%, var(--border));
}

.tag--info {
  color: var(--info);
  border-color: color-mix(in srgb, var(--info) 38%, var(--border));
}

.field__help,
.field__default {
  margin: 6px 0 0;
  color: var(--text-muted);
  font-size: 12px;
  line-height: 18px;
}

.field__default {
  margin-top: 2px;
}
</style>
