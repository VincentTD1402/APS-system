<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useApsStore } from '@/stores/aps-store'
import { useMasterStore } from '@/stores/master-store'
import Button from 'primevue/button'
import MultiSelect from 'primevue/multiselect'
import { computed, onMounted } from 'vue'
import type { RiskType } from '@/types/enums'

const { t, locale } = useI18n()
const store = useApsStore()
const master = useMasterStore()

onMounted(() => master.ensureLoaded())

// nameVi có thể null (BE không trả) → fallback về nameKo cho UI.
const wcOptions = computed(() =>
  master.workCenters.map((w) => ({
    label: locale.value === 'ko' ? w.nameKo : w.nameVi || w.nameKo,
    value: w.code,
  }))
)
const itemOptions = computed(() =>
  master.items
    .filter((i) => !i.code.startsWith('자재'))
    .map((i) => ({
      label: locale.value === 'ko' ? i.nameKo : i.nameVi || i.nameKo,
      value: i.code,
    }))
)
const riskOptions = computed<Array<{ label: string; value: RiskType }>>(() => [
  { label: t('risk.normal'), value: 'NORMAL' },
  { label: t('risk.materialShort'), value: 'MATERIAL_SHORT' },
  { label: t('risk.overload'), value: 'OVERLOAD' },
  { label: t('risk.both'), value: 'MATERIAL_AND_OVERLOAD' },
])

async function onRun(): Promise<void> {
  await store.runAps()
}
async function onApply(): Promise<void> {
  await store.applyAdjustments()
}
function onShowAll(): void {
  store.filter.cellSelection = null
  store.filter.wcCodes = []
  store.filter.itemCodes = []
  store.filter.risks = []
}
</script>

<template>
  <div class="filter-bar">
    <div class="fb-group">
      <label class="fb-label">{{ t('filter.workCenter') }}</label>
      <MultiSelect
        v-model="store.filter.wcCodes"
        :options="wcOptions"
        option-label="label"
        option-value="value"
        :placeholder="t('common.all')"
        :max-selected-labels="2"
        display="chip"
        class="fb-input"
      />
    </div>
    <div class="fb-group">
      <label class="fb-label">{{ t('filter.item') }}</label>
      <MultiSelect
        v-model="store.filter.itemCodes"
        :options="itemOptions"
        option-label="label"
        option-value="value"
        :placeholder="t('common.all')"
        :max-selected-labels="2"
        display="chip"
        class="fb-input"
      />
    </div>
    <div class="fb-group">
      <label class="fb-label">{{ t('filter.risk') }}</label>
      <MultiSelect
        v-model="store.filter.risks"
        :options="riskOptions"
        option-label="label"
        option-value="value"
        :placeholder="t('common.all')"
        :max-selected-labels="2"
        display="chip"
        class="fb-input"
      />
    </div>
    <div class="fb-spacer" />
    <Button
      :label="t('common.showAll')"
      icon="pi pi-list"
      severity="secondary"
      outlined
      @click="onShowAll"
    />
    <Button
      :label="t('common.run')"
      icon="pi pi-play"
      severity="warn"
      :loading="store.isRunning"
      @click="onRun"
    />
    <Button
      :label="t('common.apply')"
      icon="pi pi-check-square"
      severity="info"
      :badge="store.pendingCount > 0 ? String(store.pendingCount) : undefined"
      @click="onApply"
    />
  </div>
</template>

<style scoped>
.filter-bar {
  display: flex;
  align-items: end;
  gap: 12px;
  flex-wrap: wrap;
  padding: 12px 14px;
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  margin-bottom: 14px;
}
.fb-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 200px;
}
.fb-label {
  font-size: 11px;
  color: var(--p-text-muted-color);
  font-weight: 600;
}
.fb-input {
  min-width: 200px;
}
.fb-spacer {
  flex: 1;
}
</style>
