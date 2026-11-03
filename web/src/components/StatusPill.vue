<script setup lang="ts">
withDefaults(
  defineProps<{
    tone?: "success" | "warning" | "danger" | "info" | "neutral";
    label: string;
    pulse?: boolean;
  }>(),
  { tone: "neutral", pulse: false },
);
</script>

<template>
  <span class="pill" :class="[`pill--${tone}`, { 'pill--pulse': pulse }]">
    <span class="pill__dot" aria-hidden="true" />
    <span class="pill__label">{{ label }}</span>
  </span>
</template>

<style scoped>
.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--surface-2);
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
}

.pill__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentcolor;
}

.pill__label {
  font-variant-numeric: tabular-nums;
}

.pill--success {
  color: var(--success);
  border-color: color-mix(in srgb, var(--success) 40%, var(--border));
  background: color-mix(in srgb, var(--success) 12%, var(--surface));
}

.pill--warning {
  color: var(--warning);
  border-color: color-mix(in srgb, var(--warning) 40%, var(--border));
  background: color-mix(in srgb, var(--warning) 12%, var(--surface));
}

.pill--danger {
  color: var(--danger);
  border-color: color-mix(in srgb, var(--danger) 40%, var(--border));
  background: color-mix(in srgb, var(--danger) 12%, var(--surface));
}

.pill--info {
  color: var(--info);
  border-color: color-mix(in srgb, var(--info) 40%, var(--border));
  background: color-mix(in srgb, var(--info) 12%, var(--surface));
}

.pill--pulse .pill__dot {
  animation: pulse 1.6s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.35;
  }
}

@media (prefers-reduced-motion: reduce) {
  .pill--pulse .pill__dot {
    animation: none;
  }
}
</style>
