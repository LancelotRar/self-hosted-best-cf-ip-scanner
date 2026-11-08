<script setup lang="ts">
import { computed } from "vue";

import type { Param } from "../types";

const props = defineProps<{
  param: Param;
  modelValue: unknown;
  disabled?: boolean;
  /** 同组字段共用一句说明时，隐藏单字段说明，避免重复。 */
  hideHelp?: boolean;
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
  SAMPLE_SEED: { min: 0, max: 10_000_000, step: 1 },
  SEED_HOUR_FACTOR: { min: 1, max: 10_000_000, step: 1 },
  GIT_RETRY_MAX: { min: 0, max: 10, step: 1 },
  GIT_RETRY_BASE_DELAY: { min: 0, max: 600, step: 5 },
  TCP_TIMEOUT: { min: 0.5, max: 60, step: 0.5 },
};
const DEFAULT_BOUNDS = { min: 0, max: 999999, step: 1 };

/** 数字框统一为窄控件，避免每个字段各自计算宽度导致版式参差。 */
const bounds = computed(() => NUMERIC_BOUNDS[props.param.name] ?? DEFAULT_BOUNDS);

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

const listValue = computed<number[]>(() => {
  const value = props.modelValue;
  if (!Array.isArray(value)) return [];
  return value.map((item) => Number(item)).filter((item) => !Number.isNaN(item));
});

const defaultText = computed(() => {
  const value = props.param.default;
  if (Array.isArray(value)) return value.length ? value.join(", ") : "空";
  if (typeof value === "boolean") return value ? "开启" : "关闭";
  const text = String(value ?? "");
  // 没有默认值时不要留下一行孤零零的「默认」
  return text === "" ? "空" : text;
});

/** 说明里已经写了默认值时不再重复展示，避免同一行出现两次「默认」。 */
const showDefault = computed(
  () => props.param.kind !== "bool" && !props.param.help.includes("默认"),
);

/** 默认生效方式占绝大多数，重复展示只会制造噪音；只在需要额外动作时提示。 */
const effectTag = computed(() => {
  switch (props.param.effect) {
    case "restart_required":
      return { label: "需重启生效", tone: "warning" };
    case "schedule_reload":
      return { label: "保存后立即生效", tone: "info" };
    default:
      return null;
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
  <div
    class="field"
    :class="{
      'field--readonly': disabled,
      'field--wide': param.kind === 'cron' || param.kind === 'ports' || param.kind === 'csv_int',
      'field--switch': param.kind === 'bool',
    }"
  >
    <div class="field__head">
      <label class="field__label" :for="`param-${param.name}`">{{ param.label }}</label>
      <div class="field__tags">
        <span v-if="effectTag" class="tag" :class="`tag--${effectTag.tone}`">{{ effectTag.label }}</span>
        <span v-if="param.read_only" class="tag">只读</span>
        <span v-else-if="param.secret" class="tag">
          {{ param.configured ? "已配置" : "未配置" }}
        </span>
      </div>
      <span v-if="showDefault" class="field__default">默认 {{ defaultText }}</span>
    </div>

    <div class="field__control">
      <el-switch
        v-if="param.kind === 'bool'"
        :id="`param-${param.name}`"
        :model-value="Boolean(modelValue)"
        :disabled="disabled"
        :aria-describedby="`param-${param.name}-help`"
        @change="onBool"
      />

      <el-input-number
        v-else-if="param.kind === 'int' || param.kind === 'float'"
        :id="`param-${param.name}`"
        class="control control--number"
        :model-value="numberValue"
        :min="bounds.min"
        :max="bounds.max"
        :step="bounds.step"
        :precision="param.kind === 'float' ? 1 : 0"
        controls-position="right"
        :disabled="disabled"
        :aria-describedby="`param-${param.name}-help`"
        @update:model-value="onNumber"
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
    </div>

    <p v-show="!hideHelp" :id="`param-${param.name}-help`" class="field__help">
      {{ param.help }}
    </p>
  </div>
</template>

<style scoped>
.field {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.field--readonly {
  opacity: 0.82;
}

.field__head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 7px;
  flex-wrap: wrap;
  min-height: 20px;
}

.field__label {
  font-weight: 550;
  font-size: var(--fs-label);
  line-height: 20px;
}

/* 生效方式标签紧跟参数名，所有字段位置一致 */
.field__tags {
  display: flex;
  gap: var(--space-1);
  flex-wrap: wrap;
}

.tag {
  display: inline-flex;
  align-items: center;
  height: 18px;
  padding: 0 6px;
  border-radius: 4px;
  border: 1px solid transparent;
  background: var(--surface-2);
  color: var(--text-muted);
  font-size: var(--fs-micro);
  line-height: 1;
  white-space: nowrap;
}

.tag--warning {
  color: var(--warning);
  border-color: color-mix(in srgb, var(--warning) 32%, transparent);
  background: var(--tone-warning-soft);
}

.tag--info {
  color: var(--info);
  border-color: color-mix(in srgb, var(--info) 32%, transparent);
  background: var(--tone-info-soft);
}

.field__control {
  display: flex;
  align-items: center;
  min-height: 36px;
  min-width: 0;
}

.field__cron {
  display: flex;
  gap: var(--space-2);
  width: 100%;
}

.field__cron :deep(.el-input) {
  flex: 1;
}

.preset-value {
  margin-left: var(--space-2);
  color: var(--text-muted);
  font-size: var(--fs-micro);
}

.field__help {
  margin: 6px 0 0;
  color: var(--text-muted);
  font-size: var(--fs-meta);
  line-height: 18px;
}

.field__default {
  margin-left: auto;
  color: var(--text-faint);
  font-size: var(--fs-micro);
  line-height: 20px;
  white-space: nowrap;
}

.field__control :deep(.el-input),
.field__control :deep(.el-select),
.field__control :deep(.el-textarea) {
  width: 100%;
}

/* 数字输入统一为窄控件，避免逐字段计算宽度导致参差 */
.field__control :deep(.el-input-number) {
  width: 100%;
  max-width: 200px;
}

.field__control :deep(.el-select.control--short) {
  max-width: 240px;
}

/* 数字内容居中，配合右侧步进按钮 */
.field__control :deep(.el-input-number .el-input__inner) {
  text-align: center;
  padding-left: 4px;
  padding-right: 4px;
  font-variant-numeric: tabular-nums;
}

/* 开关类字段：标签与控件同一行，压缩高度 */
.field--switch .field__head {
  margin-bottom: 0;
  flex: 1 1 auto;
}

.field--switch {
  flex-direction: row;
  flex-wrap: wrap;
  align-items: center;
  column-gap: var(--space-4);
}

.field--switch .field__control {
  order: 2;
  margin-left: auto;
  min-height: 24px;
}

.field--switch .field__help {
  order: 3;
  flex: 0 0 100%;
  margin-top: 4px;
}
</style>
