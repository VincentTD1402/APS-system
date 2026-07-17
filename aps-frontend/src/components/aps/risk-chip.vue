<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { RiskType } from '@/types/enums'
import { computed } from 'vue'

const props = defineProps<{ risk: RiskType }>()
const { t } = useI18n()

const cls = computed(() => {
  switch (props.risk) {
    case 'NORMAL':
      return 'normal'
    case 'MATERIAL_SHORT':
      return 'material-short'
    case 'OVERLOAD':
      return 'overload'
    case 'MATERIAL_AND_OVERLOAD':
      return 'both'
  }
})

const label = computed(() => {
  switch (props.risk) {
    case 'NORMAL':
      return t('risk.normal')
    case 'MATERIAL_SHORT':
      return t('risk.materialShort')
    case 'OVERLOAD':
      return t('risk.overload')
    case 'MATERIAL_AND_OVERLOAD':
      return t('risk.both')
  }
})
</script>

<template>
  <span class="risk-chip" :class="cls">
    <span class="dot" />
    {{ label }}
  </span>
</template>
