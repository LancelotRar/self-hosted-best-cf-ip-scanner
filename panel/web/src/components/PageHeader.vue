<script setup lang="ts">
defineProps<{
  title: string;
  subtitle?: string;
}>();
</script>

<template>
  <header class="page-head">
    <div class="page-head__text">
      <h1 class="page-title">{{ title }}</h1>
      <p v-if="subtitle" class="page-sub">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.actions" class="page-head__actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<style scoped>
.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
  margin-bottom: var(--space-5);
}

.page-head__text {
  min-width: 0;
}

.page-head__actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding-bottom: 2px;
}

@media (max-width: 767px) {
  .page-head {
    align-items: flex-start;
  }
}
</style>
