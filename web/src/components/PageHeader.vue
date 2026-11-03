<script setup lang="ts">
import type { Component } from "vue";

defineProps<{
  title: string;
  subtitle?: string;
  icon?: Component;
}>();
</script>

<template>
  <header class="page-head">
    <span v-if="icon" class="page-head__icon" aria-hidden="true">
      <el-icon :size="18"><component :is="icon" /></el-icon>
    </span>
    <div class="page-head__text">
      <h1 class="page-title">{{ title }}</h1>
      <p v-if="subtitle" class="page-sub">{{ subtitle }}</p>
    </div>
  </header>
</template>

<style scoped>
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: flex-start;
  gap: var(--space-3);
  width: 100%;
  margin-bottom: var(--space-4);
}

.page-head__icon {
  display: inline-grid;
  place-items: center;
  flex: 0 0 auto;
  width: 36px;
  height: 36px;
  margin-top: 2px;
  border-radius: var(--radius-sm);
  border: 1px solid color-mix(in srgb, var(--primary) 30%, var(--border));
  background: color-mix(in srgb, var(--primary) 12%, var(--surface));
  color: var(--primary);
}

.page-head__text {
  min-width: 0;
}

.page-sub {
  margin-top: 4px;
}
</style>
