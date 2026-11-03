<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string;
    message: string;
    actionLabel?: string;
  }>(),
  { title: "读取失败", actionLabel: "重试" },
);

const emit = defineEmits<{ retry: [] }>();
</script>

<template>
  <div class="error" role="alert">
    <div class="error__head">
      <svg class="error__icon" viewBox="0 0 24 24" aria-hidden="true">
        <path
          d="M12 3 22 20H2L12 3Z"
          fill="none"
          stroke="currentColor"
          stroke-width="1.4"
          stroke-linejoin="round"
        />
        <path d="M12 9v5M12 17v.01" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
      </svg>
      <strong>{{ title }}</strong>
    </div>
    <p class="error__message">{{ message }}</p>
    <el-button size="small" @click="emit('retry')">{{ actionLabel }}</el-button>
  </div>
</template>

<style scoped>
.error {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  padding: var(--space-4);
  border: 1px solid color-mix(in srgb, var(--danger) 45%, var(--border));
  background: color-mix(in srgb, var(--danger) 8%, var(--surface));
  border-radius: var(--radius-md);
  color: var(--text);
}

.error__head {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--danger);
}

.error__icon {
  width: 18px;
  height: 18px;
}

.error__message {
  margin: 0;
  font-size: 13px;
  color: var(--text);
  overflow-wrap: anywhere;
}
</style>
