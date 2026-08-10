<script setup lang="ts">
import { useApsStore } from '@/stores/aps-store'

const store = useApsStore()
</script>

<template>
  <div class="kpi-row area-kpi">
    <div class="kpi-card">
      <div class="kpi-label">계획납기 준수율</div>
      <div class="kpi-value">{{ store.kpi.onTimeRatePct.toFixed(1) }}<span class="kpi-unit">%</span></div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">공정 부하율 초과</div>
      <div class="kpi-value">{{ store.kpi.overloadWcPct.toFixed(1) }}<span class="kpi-unit">%</span></div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">공정 투입 자재 부족</div>
      <div class="kpi-value">{{ store.kpi.materialShortageCount }}<span class="kpi-unit">건</span></div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">계획수립 예상 리스크</div>
      <div class="kpi-value">{{ store.kpi.planningRiskCount }}<span class="kpi-unit">건</span></div>
    </div>
  </div>
</template>
