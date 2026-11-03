<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string;
    description?: string;
    actionLabel?: string;
  }>(),
  { title: "尚无数据", description: "", actionLabel: "" },
);

const emit = defineEmits<{ action: [] }>();
</script>

<template>
  <div class="empty" role="group">
    <svg class="empty__icon" viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M4 7.5 12 3l8 4.5v9L12 21l-8-4.5v-9Z"
        fill="none"
        stroke="currentColor"
        stroke-width="1.4"
        stroke-linejoin="round"
      />
      <path d="M4 7.5 12 12l8-4.5M12 12v9" fill="none" stroke="currentColor" stroke-width="1.4" />
    </svg>
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
  gap: 8px;
  padding: 48px 16px;
  text-align: center;
  border: 1px dashed var(--border);
  border-radius: var(--radius-md);
  color: var(--text-muted);
}

.empty__icon {
  width: 32px;
  height: 32px;
  color: var(--border-strong);
}

.empty__title {
  margin: 0;
  color: var(--text);
  font-weight: 600;
}

.empty__description {
  margin: 0;
  max-width: 52ch;
  font-size: 12px;
  line-height: 18px;
}
</style>
