<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string;
    value?: string | number;
    hint?: string;
  }>(),
  { value: undefined, hint: undefined },
);
</script>

<template>
  <section class="metric">
    <span class="metric__label">{{ label }}</span>
    <div class="metric__value">
      <slot>{{ value }}</slot>
    </div>
    <p v-if="hint" class="metric__hint">{{ hint }}</p>
  </section>
</template>

<style scoped>
.metric {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: var(--space-5);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  min-height: 120px;
}

.metric__label {
  color: var(--text-muted);
  font-size: 12px;
  letter-spacing: 0.02em;
}

.metric__value {
  font-size: 20px;
  line-height: 28px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  overflow-wrap: anywhere;
}

.metric__hint {
  margin: 0;
  color: var(--text-muted);
  font-size: 12px;
  line-height: 18px;
}
</style>
