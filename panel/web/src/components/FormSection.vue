<script setup lang="ts">
defineProps<{
  title: string;
  description?: string;
}>();
</script>

<template>
  <section class="form-section">
    <header class="form-section__head">
      <div class="form-section__title-row">
        <h2 class="form-section__title">{{ title }}</h2>
        <slot name="title-extra" />
      </div>
      <p v-if="description" class="form-section__desc">{{ description }}</p>
    </header>
    <slot />
  </section>
</template>
