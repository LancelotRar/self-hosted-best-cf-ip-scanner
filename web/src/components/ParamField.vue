<script setup lang="ts">
import { computed } from "vue";
import {
  Connection,
  Document,
  Files,
  Key,
  List,
  Odometer,
  Select,
  Timer,
} from "@element-plus/icons-vue";

import type { Param } from "../types";

const props = defineProps<{
  param: Param;
  modelValue: unknown;
  disabled?: boolean;
}>();

const emit = defineEmits<{ "update:modelValue": [value: unknown] }>();

const PORT_OPTIONS = [443, 2053, 2083, 2087, 2096, 8443].map((port) => ({
  label: String(port),
  value: port,
}));

const TOPS_OPTIONS = [20, 50, 100, 200, 400, 1000].map((count) => ({
  label: String(count),
  value: count,
}));

const TIMEZONE_OPTIONS = [
  "Asia/Shanghai",
  "Asia/Tokyo",
  "Asia/Singapore",
  "Asia/Hong_Kong",
  "UTC",
  "Europe/London",
  "Europe/Berlin",
  "America/Los_Angeles",
  "America/New_York",
].map((zone) => ({ label: zone, value: zone }));

const BRANCH_OPTIONS = ["main", "master"].map((branch) => ({
  label: branch,
  value: branch,
}));

const CRON_PRESETS = [
  { label: "每 6 小时", value: "30 */6 * * *" },
  { label: "每天 03:00", value: "0 3 * * *" },
  { label: "每 2 小时", value: "0 */2 * * *" },
  { label: "每 30 分钟", value: "*/30 * * * *" },
  { label: "每 15 分钟", value: "*/15 * * * *" },
];

const NUMERIC_BOUNDS: Record<string, { min: number; max: number; step: number }> = {
  PROBE_CONCURRENCY: { min: 1, max: 1000, step: 10 },
  TCP_ATTEMPTS: { min: 1, max: 10, step: 1 },
  TCP_MIN_SUCCESS: { min: 1, max: 10, step: 1 },
  TRACE_TIMEOUT: { min: 1, max: 120, step: 1 },
  TRACE_ATTEMPTS: { min: 1, max: 10, step: 1 },
  SAMPLE_STRIDE: { min: 1, max: 65536, step: 64 },
  MAX_CANDIDATES: { min: 0, max: 100000, step: 100 },
  SAMPLE_SEED: { min: 0, max: 10_000_000, step: 1 },
  SEED_HOUR_FACTOR: { min: 1, max: 10_000_000, step: 1 },
  PUID: { min: 0, max: 65535, step: 1 },
  PGID: { min: 0, max: 65535, step: 1 },
  GIT_RETRY_MAX: { min: 0, max: 10, step: 1 },
  GIT_RETRY_BASE_DELAY: { min: 0, max: 600, step: 5 },
  TCP_TIMEOUT: { min: 0.5, max: 60, step: 0.5 },
};
const DEFAULT_BOUNDS = { min: 0, max: 999999, step: 1 };

const bounds = computed(() => NUMERIC_BOUNDS[props.param.name] ?? DEFAULT_BOUNDS);

const KIND_ICONS = {
  bool: Select,
  int: Odometer,
  float: Odometer,
  ports: Connection,
  csv_int: List,
  cron: Timer,
  secret: Key,
  path: Files,
  str: Document,
} as const;

const kindIcon = computed(() => KIND_ICONS[props.param.kind as keyof typeof KIND_ICONS] ?? Document);

const disabled = computed(() => props.disabled || props.param.read_only);

const textValue = computed(() => {
  const value = props.modelValue;
  if (Array.isArray(value)) return value.join(",");
  if (value === null || value === undefined) return "";
  return String(value);
});

const numberValue = computed(() =>
  typeof props.modelValue === "number" ? props.modelValue : Number(props.modelValue) || 0,
);

/** 数字框宽度按内容长度自适应，避免固定宽度造成的空洞或截断。 */
const numberWidth = computed(() => {
  const values = [numberValue.value, props.param.default, bounds.value.min].map((value) =>
    String(value ?? ""),
  );
  const digits = Math.max(3, ...values.map((value) => value.length));
  return `calc(${digits + 2}ch + 44px)`;
});

const listValue = computed<number[]>(() => {
  const value = props.modelValue;
  if (!Array.isArray(value)) return [];
  return value.map((item) => Number(item)).filter((item) => !Number.isNaN(item));
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

function onNumber(value: number | undefined) {
  emit("update:modelValue", typeof value === "number" && !Number.isNaN(value) ? value : 0);
}

function onList(value: Array<number | string>) {
  emit(
    "update:modelValue",
    value
      .map((item) => Number(item))
      .filter((item) => !Number.isNaN(item)),
  );
}

function onBool(value: string | number | boolean) {
  emit("update:modelValue", Boolean(value));
}
</script>

<template>
  <div class="field" :class="{ 'field--readonly': disabled }">
    <div class="field__head">
      <label class="field__label" :for="`param-${param.name}`">
        <el-icon class="field__kind" :size="14" aria-hidden="true">
          <component :is="kindIcon" />
        </el-icon>
        {{ param.label }}
      </label>
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

    <el-input-number
      v-else-if="param.kind === 'int' || param.kind === 'float'"
      :id="`param-${param.name}`"
      class="control control--number"
      :style="{ width: numberWidth }"
      :model-value="numberValue"
      :min="bounds.min"
      :max="bounds.max"
      :step="bounds.step"
      :precision="param.kind === 'float' ? 1 : 0"
      controls-position="right"
      :disabled="disabled"
      :aria-describedby="`param-${param.name}-help`"
      @change="onNumber"
    />

    <el-select
      v-else-if="param.kind === 'ports'"
      :id="`param-${param.name}`"
      class="control control--select"
      :model-value="listValue"
      multiple
      filterable
      allow-create
      default-first-option
      :disabled="disabled"
      placeholder="选择或输入端口"
      :aria-describedby="`param-${param.name}-help`"
      @change="onList"
    >
      <el-option
        v-for="option in PORT_OPTIONS"
        :key="option.value"
        :label="option.label"
        :value="option.value"
      />
    </el-select>

    <el-select
      v-else-if="param.kind === 'csv_int'"
      :id="`param-${param.name}`"
      class="control control--select"
      :model-value="listValue"
      multiple
      filterable
      allow-create
      default-first-option
      :disabled="disabled"
      placeholder="选择或输入条数"
      :aria-describedby="`param-${param.name}-help`"
      @change="onList"
    >
      <el-option
        v-for="option in TOPS_OPTIONS"
        :key="option.value"
        :label="option.label"
        :value="option.value"
      />
    </el-select>

    <div v-else-if="param.kind === 'cron'" class="field__cron">
      <el-input
        :id="`param-${param.name}`"
        class="mono"
        :model-value="textValue"
        :disabled="disabled"
        :aria-describedby="`param-${param.name}-help`"
        @input="onText"
      />
      <el-dropdown trigger="click" :disabled="disabled">
        <el-button :disabled="disabled">常用模板</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item
              v-for="preset in CRON_PRESETS"
              :key="preset.value"
              @click="onText(preset.value)"
            >
              {{ preset.label }}
              <span class="mono preset-value">{{ preset.value }}</span>
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <el-select
      v-else-if="param.name === 'TZ'"
      :id="`param-${param.name}`"
      class="control control--select control--short"
      :model-value="textValue"
      filterable
      allow-create
      default-first-option
      :disabled="disabled"
      placeholder="选择时区"
      :aria-describedby="`param-${param.name}-help`"
      @change="onText"
    >
      <el-option
        v-for="option in TIMEZONE_OPTIONS"
        :key="option.value"
        :label="option.label"
        :value="option.value"
      />
    </el-select>

    <el-select
      v-else-if="param.name === 'GIT_BRANCH'"
      :id="`param-${param.name}`"
      class="control control--select control--short"
      :model-value="textValue"
      filterable
      allow-create
      default-first-option
      :disabled="disabled"
      placeholder="选择或输入分支"
      :aria-describedby="`param-${param.name}-help`"
      @change="onText"
    >
      <el-option
        v-for="option in BRANCH_OPTIONS"
        :key="option.value"
        :label="option.label"
        :value="option.value"
      />
    </el-select>

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
      :class="{ mono: param.kind === 'path' }"
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
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  font-size: 13px;
}

.field__kind {
  color: var(--text-muted);
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

.field__cron {
  display: flex;
  gap: var(--space-2);
}

.field__cron :deep(.el-input) {
  flex: 1;
}

.preset-value {
  margin-left: var(--space-2);
  color: var(--text-muted);
  font-size: 11px;
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

.field :deep(.el-input-number) {
  max-width: 100%;
}

/* 数字内容居中，宽度随内容自适应 */
.field :deep(.el-input-number .el-input__inner) {
  text-align: center;
  padding-left: 4px;
  padding-right: 4px;
}

.field :deep(.el-select) {
  width: 100%;
  max-width: 560px;
}

.field :deep(.el-select.control--short) {
  max-width: 340px;
}
</style>
