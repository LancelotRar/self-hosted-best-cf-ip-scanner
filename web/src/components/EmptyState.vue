<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string;
    description?: string;
    retryLabel?: string;
  }>(),
  {
    title: "尚无数据",
    description: "",
    retryLabel: "重试",
  },
);

const emit = defineEmits<{ retry: [] }>();
</script>

<template>
  <div class="empty">
    <el-empty :description="description || title">
      <el-button v-if="retryLabel" @click="emit('retry')">{{ retryLabel }}</el-button>
    </el-empty>
  </div>
</template>

<style scoped>
.empty {
  padding: 8px 0;
}
</style>
