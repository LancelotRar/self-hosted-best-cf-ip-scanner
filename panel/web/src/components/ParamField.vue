<script setup lang="ts">
import { computed } from "vue";

import HintIcon from "./HintIcon.vue";
import type { Param } from "../types";

const props = defineProps<{
  param: Param;
  modelValue: unknown;
  disabled?: boolean;
  /** 后端字段级校验错误；显示在控件下方。 */
  error?: string;
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

/** 字段在 12 列栅格里的跨度：数字紧凑、短文本适中、长 URL/令牌整行。 */
const SPAN_BY_NAME: Record<string, string> = {
  PROBE_HOST: "field--half",
  LOCATIONS_FILE: "field--short",
  LIBRARY_FILE: "field--short",
  PINNED_FILE: "field--short",
  DETAIL_CSV_NAME: "field--short",
  PINNED_OUTPUT_NAME: "field--short",
  GIT_BRANCH: "field--half",
  GIT_OUTPUT_SUBDIR: "field--half",
  TZ: "field--short",
  GIT_AUTHOR_NAME: "field--medium",
  GIT_AUTHOR_EMAIL: "field--medium",
  GIT_REPO_URL: "field--half",
  GIT_TOKEN: "field--half",
  HTTP_PROXY: "field--half",
  HTTPS_PROXY: "field--half",
  ALL_PROXY: "field--half",
  NO_PROXY: "field--half",
  no_proxy: "field--half",
};

const THIRD_NAMES = new Set([
  "SAMPLE_STRIDE",
  "SAMPLE_SEED",
  "SEED_HOUR_FACTOR",
]);

const spanClass = computed(() => {
  const { kind, name } = props.param;
  if (name === "PROBE_PORTS") return "field--half";
  if (name === "OVERALL_TOPS") return "field--full";
  if (name.startsWith("TOP_") || THIRD_NAMES.has(name)) return "field--third";
  if (kind === "bool" || kind === "cron") return "field--full";
  if (kind === "int" || kind === "float") return "field--compact";
  if (kind === "ports" || kind === "csv_int") return "field--half";
  return SPAN_BY_NAME[name] ?? "field--full";
});

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

/** 说明里已经写了默认值时不再重复展示；空默认值和密钥不显示默认。 */
const showDefault = computed(() => {
  const value = props.param.default;
  const empty =
    value === "" ||
    value === null ||
    value === undefined ||
    (Array.isArray(value) && value.length === 0);
  return (
    props.param.kind !== "bool" &&
    props.param.kind !== "secret" &&
    !empty &&
    !props.param.help.includes("默认")
  );
});

const hintText = computed(() =>
  showDefault.value
    ? `${props.param.help}（默认 ${defaultText.value}）`
    : props.param.help,
);

const hintId = computed(() => `param-${props.param.name}-hint`);

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
    :class="[
      spanClass,
      {
        'field--readonly': disabled,
        'field--error': Boolean(error),
        'field--switch': param.kind === 'bool',
        'field--ports': param.kind === 'ports',
      },
    ]"
  >
    <div class="field__head">
      <label class="field__label" :for="`param-${param.name}`">{{ param.label }}</label>
      <HintIcon :content="hintText" :label="`查看「${param.label}」说明`" />
      <div class="field__tags">
        <span v-if="effectTag" class="tag" :class="`tag--${effectTag.tone}`">{{ effectTag.label }}</span>
        <span v-if="param.read_only" class="tag">只读</span>
        <span v-else-if="param.secret" class="tag">
          {{ param.configured ? "已配置" : "未配置" }}
        </span>
      </div>
      <span :id="hintId" class="sr-only">{{ hintText }}</span>
    </div>

    <div class="field__control">
      <el-switch
        v-if="param.kind === 'bool'"
        :id="`param-${param.name}`"
        :model-value="Boolean(modelValue)"
        :disabled="disabled"
        :aria-label="param.label"
        :aria-invalid="Boolean(error) || undefined"
        :aria-describedby="hintId"
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
        :aria-label="param.label"
        :aria-invalid="Boolean(error) || undefined"
        :aria-describedby="hintId"
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
        :aria-label="param.label"
        :aria-invalid="Boolean(error) || undefined"
        :aria-describedby="hintId"
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
        :aria-label="param.label"
        :aria-invalid="Boolean(error) || undefined"
        :aria-describedby="hintId"
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
          :aria-label="param.label"
        :aria-invalid="Boolean(error) || undefined"
        :aria-describedby="hintId"
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
        class="control control--select"
        :model-value="textValue"
        filterable
        allow-create
        default-first-option
        :disabled="disabled"
        placeholder="选择时区"
        :aria-label="param.label"
        :aria-invalid="Boolean(error) || undefined"
        :aria-describedby="hintId"
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
        class="control control--select"
        :model-value="textValue"
        filterable
        allow-create
        default-first-option
        :disabled="disabled"
        placeholder="选择或输入分支"
        :aria-label="param.label"
        :aria-invalid="Boolean(error) || undefined"
        :aria-describedby="hintId"
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
        :aria-label="param.label"
        :aria-invalid="Boolean(error) || undefined"
        :aria-describedby="hintId"
        @input="onText"
      />

      <el-input
        v-else
        :id="`param-${param.name}`"
        :class="{ mono: param.kind === 'path' }"
        :model-value="textValue"
        :disabled="disabled"
        :aria-label="param.label"
        :aria-invalid="Boolean(error) || undefined"
        :aria-describedby="hintId"
        @input="onText"
      />
    </div>

    <p v-if="error" class="field__error" role="alert">{{ error }}</p>
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

.field__error {
  margin: 4px 0 0;
  color: var(--danger);
  font-size: var(--fs-meta);
  line-height: 18px;
}

.field--error :deep(.el-input__wrapper),
.field--error :deep(.el-textarea__inner),
.field--error :deep(.el-select__wrapper) {
  box-shadow: 0 0 0 1px var(--danger) inset;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.field__control :deep(.el-input),
.field__control :deep(.el-select),
.field__control :deep(.el-textarea) {
  width: 100%;
}

/* 控件一律撑满字段宽度：输入框左右顶到卡片边缘，不在卡片里留死角 */
.field__control :deep(.el-input-number) {
  width: 100%;
}

/* 数字左对齐，配合右侧步进按钮，长输入框里不会出现居中悬浮感 */
.field__control :deep(.el-input-number .el-input__inner) {
  text-align: left;
  padding-left: 12px;
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
</style>
