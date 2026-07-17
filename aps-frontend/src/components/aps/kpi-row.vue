<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { KpiSnapshot } from '@/types/aps'

defineProps<{ kpi: KpiSnapshot | null }>()
const { t } = useI18n()
</script>

<template>
  <div class="kpi-row">
    <div class="kpi-card ok">
      <div class="kpi-label">{{ t('kpi.onTime') }}</div>
      <div class="kpi-value">
        {{ kpi ? kpi.onTimeRatePct.toFixed(1) : '—' }}<span>{{ t('kpi.unitPct') }}</span>
      </div>
    </div>
    <div class="kpi-card mat">
      <div class="kpi-label">{{ t('kpi.materialShort') }}</div>
      <div class="kpi-value">
        {{ kpi ? kpi.materialShortageCount : '—' }}<span>{{ t('kpi.unitCase') }}</span>
      </div>
    </div>
    <div class="kpi-card cap">
      <div class="kpi-label">{{ t('kpi.overloadWc') }}</div>
      <div class="kpi-value">
        {{ kpi ? kpi.overloadWcPct.toFixed(1) : '—' }}<span>{{ t('kpi.unitWc') }}</span>
      </div>
    </div>
    <div class="kpi-card crit">
      <div class="kpi-label">{{ t('kpi.planRisk') }}</div>
      <div class="kpi-value">
        {{ kpi ? kpi.planningRiskCount : '—' }}<span>{{ t('kpi.unitCase') }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}
.kpi-card {
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  padding: 14px 16px;
  position: relative;
  overflow: hidden;
}
.kpi-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--k-color);
}
.kpi-card.ok {
  --k-color: var(--aps-ok);
}
.kpi-card.mat {
  --k-color: var(--aps-mat);
}
.kpi-card.cap {
  --k-color: var(--aps-cap);
}
.kpi-card.crit {
  --k-color: var(--aps-crit);
}
.kpi-label {
  font-size: 12px;
  color: var(--p-text-muted-color);
  font-weight: 600;
  margin-bottom: 8px;
}
.kpi-value {
  font-family: var(--aps-mono);
  font-size: 26px;
  font-weight: 700;
}
.kpi-value span {
  font-size: 13px;
  color: var(--p-text-muted-color);
  font-weight: 500;
  margin-left: 3px;
}
.kpi-card.ok .kpi-value {
  color: var(--aps-ok);
}
.kpi-card.mat .kpi-value {
  color: var(--aps-mat);
}
.kpi-card.cap .kpi-value {
  color: var(--aps-cap);
}
.kpi-card.crit .kpi-value {
  color: var(--aps-crit);
}
</style>
