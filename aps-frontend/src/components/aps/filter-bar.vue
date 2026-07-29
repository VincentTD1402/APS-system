<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useApsStore } from '@/stores/aps-store'
import { useMasterStore } from '@/stores/master-store'
import Button from 'primevue/button'
import MultiSelect from 'primevue/multiselect'
import DatePicker from 'primevue/datepicker'
import { computed, onMounted, ref, watch } from 'vue'
import { useToast } from 'primevue/usetoast'
import type { RiskType } from '@/types/enums'
import DispatchWorkOrderDialog from './dialogs/dispatch-work-order-dialog.vue'

const { t, locale } = useI18n()
const store = useApsStore()
const master = useMasterStore()
const toast = useToast()
const dispatchDialog = ref(false)

// Two separate single-date pickers (start / end) instead of one range picker
// — the store keeps plain "yyyy-mm-dd" strings (same format the backend
// filters/WorkPlan dates use), so convert at the edge.
const dateFromPick = ref<Date | null>(null)
const dateToPick = ref<Date | null>(null)
function toIsoDate(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
const isDateRangeInvalid = computed(() => {
  if (!dateFromPick.value || !dateToPick.value) return false
  return dateToPick.value < dateFromPick.value
})

// Invalid range (end < start) is never sent to the store filter — keeping the
// prior valid dateTo out of filteredPlans's overlap test instead of silently
// filtering against a nonsensical range.
watch(dateFromPick, (d) => { store.filter.dateFrom = d ? toIsoDate(d) : null })
watch([dateFromPick, dateToPick], ([, d]) => {
  store.filter.dateTo = d && !isDateRangeInvalid.value ? toIsoDate(d) : null
})

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
async function onDispatchConfirmed(planIds: string[]): Promise<void> {
  let okCount = 0
  for (const planId of planIds) {
    try {
      await store.dispatchWorkOrder(planId)
      okCount++
    } catch {
      // continue dispatching the rest; failures are surfaced via the toast count below
    }
  }
  toast.add({
    severity: okCount === planIds.length ? 'success' : 'warn',
    summary: t('detail.createWorkOrder'),
    detail: `${okCount}/${planIds.length}`,
    life: 3000,
  })
}
function onShowAll(): void {
  store.filter.cellSelection = null
  store.filter.wcCodes = []
  store.filter.itemCodes = []
  store.filter.risks = []
  store.filter.dateFrom = null
  store.filter.dateTo = null
  dateFromPick.value = null
  dateToPick.value = null
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
    <div class="fb-group">
      <label class="fb-label">{{ t('filter.completionFrom') }}</label>
      <DatePicker
        v-model="dateFromPick"
        date-format="yy-mm-dd"
        show-icon
        show-button-bar
        :placeholder="t('common.all')"
        class="fb-input"
      />
    </div>
    <div class="fb-group">
      <label class="fb-label">{{ t('filter.completionTo') }}</label>
      <DatePicker
        v-model="dateToPick"
        date-format="yy-mm-dd"
        show-icon
        show-button-bar
        :min-date="dateFromPick ?? undefined"
        :placeholder="t('common.all')"
        class="fb-input"
        :invalid="isDateRangeInvalid"
      />
      <small v-if="isDateRangeInvalid" class="fb-error">{{ t('common.invalidDateRange') }}</small>
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
    <Button
      :label="t('detail.createWorkOrder')"
      icon="pi pi-check-circle"
      severity="success"
      :badge="store.pendingPurchaseCount > 0 ? String(store.pendingPurchaseCount) : undefined"
      :disabled="store.filteredPlans.length === 0"
      @click="dispatchDialog = true"
    />
  </div>
  <DispatchWorkOrderDialog v-model:visible="dispatchDialog" @confirm="onDispatchConfirmed" />
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
.fb-error {
  color: var(--p-red-500, #ef4444);
  font-size: 11px;
}
.fb-spacer {
  flex: 1;
}
</style>
