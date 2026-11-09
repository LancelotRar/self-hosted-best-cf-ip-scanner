<script setup lang="ts">
import { computed, ref } from "vue";
import { QuestionFilled } from "@element-plus/icons-vue";

/**
 * 参数名右侧的小问号：二级说明、默认值、格式约定都收进悬停提示，
 * 版面只留标签与控件，避免说明文字把字段挤成参差的行高。
 */
const props = defineProps<{
  /** 单行说明；与 paragraphs 二选一。 */
  content?: string;
  /** 多行说明，每项一段。 */
  paragraphs?: string[];
  /** 无障碍名称；默认取说明首句。 */
  label?: string;
  /** 图标尺寸，默认 13。 */
  size?: number;
  /** 气泡方向：靠近页头的标题用 bottom，避免盖住导航与标签栏。 */
  placement?: "top" | "bottom";
}>();

const open = ref(false);

const accessibleLabel = computed(() => {
  if (props.label) return props.label;
  const first = props.paragraphs?.[0] ?? props.content ?? "";
  return first ? `查看说明：${first}` : "查看说明";
});
</script>

<template>
  <el-tooltip
    :visible="open"
    :placement="placement ?? 'top'"
    effect="light"
    popper-class="param-hint-popper"
  >
    <template #content>
      <template v-if="paragraphs?.length">
        <p v-for="(line, index) in paragraphs" :key="index" class="hint-icon__line">
          {{ line }}
        </p>
      </template>
      <span v-else>{{ content }}</span>
    </template>
    <button
      type="button"
      class="hint-icon"
      :aria-label="accessibleLabel"
      @mouseenter="open = true"
      @mouseleave="open = false"
      @focus="open = true"
      @blur="open = false"
      @click.stop
      @keydown.esc="open = false"
    >
      <el-icon :size="size ?? 13"><QuestionFilled /></el-icon>
    </button>
  </el-tooltip>
</template>

<style scoped>
.hint-icon {
  display: inline-grid;
  flex: none;
  place-items: center;
  width: 16px;
  height: 16px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: none;
  color: var(--text-faint);
  cursor: help;
  line-height: 1;
  transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease);
}

.hint-icon:hover,
.hint-icon:focus-visible {
  color: var(--text);
  background: var(--surface-2);
}

.hint-icon:focus-visible {
  outline: 2px solid var(--primary);
  outline-offset: 1px;
}

.hint-icon :deep(.el-icon) {
  color: inherit;
  pointer-events: none;
}

.hint-icon__line {
  margin: 0;
}

.hint-icon__line + .hint-icon__line {
  margin-top: 6px;
}
</style>
