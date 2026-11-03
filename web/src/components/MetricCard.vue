<script setup lang="ts">
import type { Component } from "vue";

withDefaults(
  defineProps<{
    label: string;
    value?: string | number;
    hint?: string;
    icon?: Component;
    flat?: boolean;
  }>(),
  { value: undefined, hint: undefined, icon: undefined, flat: false },
);
</script>

<template>
  <section class="metric" :class="{ 'metric--flat': flat }">
    <div class="metric__head">
      <span v-if="icon" class="metric__icon" aria-hidden="true">
        <el-icon :size="16"><component :is="icon" /></el-icon>
      </span>
      <span class="metric__label">{{ label }}</span>
    </div>
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
  gap: 10px;
  padding: var(--space-5);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow);
  min-height: 120px;
}

.metric--flat {
  padding: 18px 20px;
  min-height: 0;
  border: none;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.metric__head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.metric__icon {
  display: inline-grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  color: var(--text-muted);
}

.metric__label {
  color: var(--text-muted);
  font-size: 12px;
  letter-spacing: 0.02em;
}

.metric__value {
  font-family: var(--font-mono);
  font-size: 22px;
  line-height: 30px;
  font-weight: 600;
  letter-spacing: -0.02em;
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
