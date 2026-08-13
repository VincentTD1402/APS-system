<script setup lang="ts">
// Badge 3-state cho 1 row đã 확인: 대기중 (chưa sim) / 해결됨 (sim + risk hết) / 미해결 (sim + risk còn).
import { useI18n } from 'vue-i18n'

interface Props {
  state: 'pending' | 'solved' | 'unresolved' | null | undefined
}
const props = defineProps<Props>()

const { t } = useI18n()

const LABEL_KEY: Record<'pending' | 'solved' | 'unresolved', string> = {
  pending: 'badge.pending',
  solved: 'badge.solved',
  unresolved: 'badge.unresolved',
}
</script>

<template>
  <span v-if="props.state" :class="['badge-tag', `badge-${props.state}`]">
    {{ t(LABEL_KEY[props.state]) }}
  </span>
</template>

<style scoped>
.badge-tag {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 500;
  vertical-align: middle;
  border: 1px solid transparent;
}
.badge-pending    { color: #b26a00; background: #fff4e5; border-color: #ffcc80; }
.badge-solved     { color: #2e7d32; background: #e8f5e9; border-color: #a5d6a7; }
.badge-unresolved { color: #c62828; background: #ffebee; border-color: #ef9a9a; }
</style>
