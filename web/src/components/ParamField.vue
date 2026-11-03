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

const effectLabel = computed(() => {
  switch (props.param.effect) {
    case "restart_required":
      return "需重启";
    case "schedule_reload":
      return "热重载";
    default:
      return "下一轮";
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
  <div class="param-field">
    <div class="param-field__head">
      <label class="param-field__label" :for="`param-${param.name}`">{{ param.label }}</label>
      <div class="param-field__tags">
        <el-tag
          size="small"
          :type="param.effect === 'restart_required' ? 'warning' : param.effect === 'schedule_reload' ? 'primary' : 'success'"
        >
          {{ effectLabel }}
        </el-tag>
        <el-tag size="small" :type="param.source === 'dotenv' ? 'warning' : 'info'">
          {{ param.source === "dotenv" ? "来自 .env" : "默认值" }}
        </el-tag>
        <el-tag v-if="param.read_only" size="small" type="info">只读</el-tag>
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
      @input="onNumber"
    />
    <el-input
      v-else-if="param.kind === 'ports' || param.kind === 'csv_int'"
      :id="`param-${param.name}`"
      :model-value="textValue"
      :disabled="disabled"
      placeholder="逗号分隔，例如 443,2053"
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
      @input="onText"
    />
    <el-input
      v-else
      :id="`param-${param.name}`"
      :model-value="textValue"
      :disabled="disabled"
      @input="onText"
    />

    <p class="panel-muted param-field__help">{{ param.help }}</p>
    <p class="panel-muted param-field__default">
      默认：{{ Array.isArray(param.default) ? param.default.join(",") : String(param.default) }}
    </p>
  </div>
</template>

<style scoped>
.param-field {
  padding: 10px 0;
  border-bottom: 1px dashed var(--panel-border);
}

.param-field:last-child {
  border-bottom: none;
}

.param-field__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
}

.param-field__label {
  font-weight: 600;
}

.param-field__tags {
  display: flex;
  gap: 4px;
}

.param-field__help {
  margin: 6px 0 0;
  font-size: 12px;
}

.param-field__default {
  margin: 2px 0 0;
  font-size: 12px;
}
</style>
