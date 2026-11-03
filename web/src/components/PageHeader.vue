<script setup lang="ts">
defineProps<{
  title: string;
  subtitle?: string;
}>();
</script>

<template>
  <header class="page-head">
    <h1 class="page-title">{{ title }}</h1>
    <p v-if="subtitle" class="page-sub">{{ subtitle }}</p>
  </header>
</template>

<style scoped>
.page-head {
  display: block;
  width: 100%;
  margin-bottom: var(--space-4);
}

.page-title {
  margin: 0;
  font-size: 20px;
  line-height: 28px;
  font-weight: 600;
  letter-spacing: 0.01em;
  text-align: left;
}

.page-sub {
  margin: 6px 0 0;
  color: var(--text-muted);
  font-size: 13px;
  line-height: 20px;
  text-align: left;
}
</style>
