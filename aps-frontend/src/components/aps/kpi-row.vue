<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useApsStore } from '@/stores/aps-store'

const store = useApsStore()
const { t } = useI18n()
</script>

<template>
  <div class="kpi-row area-kpi">
    <div class="kpi-card">
      <div class="kpi-label">{{ t('kpi.onTime') }}</div>
      <div class="kpi-value">{{ store.kpi.onTimeRatePct.toFixed(1) }}<span class="kpi-unit">{{ t('kpi.unitPct') }}</span></div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">{{ t('kpi.overloadWc') }}</div>
      <div class="kpi-value">{{ store.kpi.overloadWcPct.toFixed(1) }}<span class="kpi-unit">{{ t('kpi.unitPct') }}</span></div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">{{ t('kpi.materialShort') }}</div>
      <div class="kpi-value">{{ store.kpi.materialShortageCount }}<span class="kpi-unit">{{ t('kpi.unitCase') }}</span></div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">{{ t('kpi.planRisk') }}</div>
      <div class="kpi-value">{{ store.kpi.planningRiskCount }}<span class="kpi-unit">{{ t('kpi.unitCase') }}</span></div>
    </div>
  </div>
</template>
