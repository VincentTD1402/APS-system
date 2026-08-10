<script setup lang="ts">
defineProps<{ message: string; visible: boolean }>()
</script>

<template>
  <div v-if="visible" class="toast" role="status" aria-live="polite">{{ message }}</div>
</template>

<style scoped>
.toast {
  position: fixed;
  top: 24px;
  left: 50%;
  transform: translateX(-50%);
  background: #222;
  color: #fff;
  padding: 10px 18px;
  border-radius: 6px;
  font-size: 13px;
  z-index: 9999;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  pointer-events: none;
}
</style>
