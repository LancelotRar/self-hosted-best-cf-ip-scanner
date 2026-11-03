<script setup lang="ts">
defineProps<{
  modelValue: boolean;
  description?: string;
}>();

const emit = defineEmits<{
  "update:modelValue": [boolean];
  discard: [];
}>();
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="未保存的修改"
    width="440px"
    align-center
    :close-on-click-modal="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <p class="unsaved__text">
      {{ description ?? "有未保存的修改，离开后这些修改会丢失。" }}
    </p>
    <template #footer>
      <div class="unsaved__actions">
        <el-button @click="emit('update:modelValue', false)">继续编辑</el-button>
        <el-button type="danger" @click="emit('discard')">放弃修改</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.unsaved__text {
  margin: 0;
  color: var(--text-muted);
  font-size: 13px;
  line-height: 20px;
}

.unsaved__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}
</style>
