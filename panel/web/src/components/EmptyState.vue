<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string;
    description?: string;
    actionLabel?: string;
    /** 嵌在卡片/表格里的空态：降低高度，避免把整页撑空。 */
    compact?: boolean;
  }>(),
  { title: "尚无数据", description: "", actionLabel: "", compact: false },
);

const emit = defineEmits<{ action: [] }>();
</script>

<template>
  <div class="empty" :class="{ 'empty--compact': compact }" role="group">
    <span class="empty__badge" aria-hidden="true">
      <svg class="empty__icon" viewBox="0 0 24 24">
        <path
          d="M4 7.5 12 3l8 4.5v9L12 21l-8-4.5v-9Z"
          fill="none"
          stroke="currentColor"
          stroke-width="1.4"
          stroke-linejoin="round"
        />
        <path d="M4 7.5 12 12l8-4.5M12 12v9" fill="none" stroke="currentColor" stroke-width="1.4" />
      </svg>
    </span>
    <p class="empty__title">{{ title }}</p>
    <p v-if="description" class="empty__description">{{ description }}</p>
    <el-button v-if="actionLabel" size="small" @click="emit('action')">{{ actionLabel }}</el-button>
  </div>
</template>

<style scoped>
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 40px 16px;
  text-align: center;
  border: 1px dashed var(--border);
  border-radius: var(--radius-md);
  color: var(--text-muted);
}

.empty__badge {
  display: inline-grid;
  place-items: center;
  width: 40px;
  height: 40px;
  margin-bottom: 2px;
  border-radius: 50%;
  background: var(--surface-2);
  color: var(--text-faint);
}

.empty__icon {
  width: 20px;
  height: 20px;
}

.empty__title {
  margin: 0;
  color: var(--text);
  font-size: var(--fs-body);
  font-weight: 600;
}

.empty__description {
  margin: 0;
  max-width: 52ch;
  font-size: var(--fs-meta);
  line-height: 18px;
}

.empty--compact {
  padding: 24px 16px;
  gap: 4px;
}

.empty--compact .empty__badge {
  width: 32px;
  height: 32px;
}

.empty--compact .empty__icon {
  width: 17px;
  height: 17px;
}

.empty .el-button {
  margin-top: 6px;
}
</style>
