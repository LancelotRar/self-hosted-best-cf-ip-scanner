<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";

const route = useRoute();
const title = computed(() => String(route.meta.title ?? "功能"));
</script>

<template>
  <section class="panel-page">
    <div class="panel-page__title">
      <h1>{{ title }}</h1>
    </div>
    <el-empty :description="`${title}页面正在建设中`" />
  </section>
</template>
