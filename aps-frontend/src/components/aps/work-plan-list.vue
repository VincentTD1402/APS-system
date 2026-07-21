<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useApsStore } from '@/stores/aps-store'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import RiskChip from './risk-chip.vue'
import { computed } from 'vue'
import type { WorkPlan } from '@/types/planning'
import type { RiskType } from '@/types/enums'

const { t, locale } = useI18n()
const store = useApsStore()

const selectedCellStatus = computed(() => {
  const sel = store.filter.cellSelection
  if (!sel) return null
  return (
    store.loadCells.find((c) => c.wcCode === sel.wcCode && c.cellDate === sel.date)?.status ?? null
  )
})

function contextualRisk(plan: WorkPlan): RiskType {
  const cellStatus = selectedCellStatus.value
  if (!cellStatus) return plan.riskType
  // Filter theo cell → risk chip phản ánh trạng thái tại cell đó, không phải plan-level
  const cellOverload =
    cellStatus === 'OVERLOAD' || cellStatus === 'OVERLOAD_AND_MATERIAL_SHORT'
  const cellMaterialShort =
    cellStatus === 'MATERIAL_SHORT' || cellStatus === 'OVERLOAD_AND_MATERIAL_SHORT'
  if (cellOverload && cellMaterialShort) return 'MATERIAL_AND_OVERLOAD'
  if (cellOverload) return 'OVERLOAD'
  if (cellMaterialShort) return 'MATERIAL_SHORT'
  return 'NORMAL'
}

const rows = computed(() => {
  const rank: Record<string, number> = {
    MATERIAL_AND_OVERLOAD: 0,
    OVERLOAD: 1,
    MATERIAL_SHORT: 2,
    NORMAL: 3,
  }
  return [...store.filteredPlans].sort((a, b) => {
    const r = rank[contextualRisk(a)] - rank[contextualRisk(b)]
    if (r !== 0) return r
    return a.planStartDate.localeCompare(b.planStartDate)
  })
})

function onRowSelect(evt: { data: WorkPlan }): void {
  store.selectedPlanId = evt.data.id
}

const selectedRow = computed(() => rows.value.find((r) => r.id === store.selectedPlanId) ?? null)
</script>

<template>
  <div class="panel">
    <div class="panel-head">
      <div>
        <div class="panel-title">{{ t('workPlanList.title') }}</div>
        <div class="panel-sub">
          {{ t('workPlanList.subtitle', { total: rows.length, risk: store.riskCount, delay: store.delayCount }) }}
        </div>
      </div>
    </div>
    <DataTable
      :value="rows"
      :selection="selectedRow"
      selection-mode="single"
      data-key="id"
      scrollable
      scroll-height="360px"
      size="small"
      striped-rows
      @row-select="onRowSelect"
    >
      <Column :header="t('workPlanList.col.workOrderNo')" field="workOrderNo" class="mono">
        <template #body="{ data }">
          <span class="mono">{{ data.workOrderNo ?? '—' }}</span>
        </template>
      </Column>
      <Column :header="t('workPlanList.col.tmpPlanNo')" field="tmpPlanNo" class="mono">
        <template #body="{ data }">
          <span class="mono">{{ data.tmpPlanNo ?? '—' }}</span>
        </template>
      </Column>
      <Column :header="t('workPlanList.col.orderNo')" field="orderNo" class="mono" />
      <Column :header="t('workPlanList.col.item')">
        <template #body="{ data }">
          {{ locale === 'ko' ? data.itemNameKo : data.itemNameVi }}
        </template>
      </Column>
      <Column :header="t('workPlanList.col.wc')">
        <template #body="{ data }">
          {{ data.wcName ?? (data.wcCode || '—') }}
        </template>
      </Column>
      <Column :header="t('workPlanList.col.process')">
        <template #body="{ data }">
          {{ locale === 'ko' ? data.processNameKo : data.processNameVi }}
        </template>
      </Column>
      <Column :header="t('workPlanList.col.planQty')" field="planQty">
        <template #body="{ data }">
          <span class="mono">{{ data.planQty.toLocaleString() }}</span>
        </template>
      </Column>
      <Column :header="t('workPlanList.col.planStart')" field="planStartDate">
        <template #body="{ data }">
          <span class="mono">{{ data.planStartDate }}</span>
          <Tag v-if="data.adjusted" severity="warn" value="adj" class="ml-1" />
        </template>
      </Column>
      <Column :header="t('workPlanList.col.planEnd')" field="planEndDate">
        <template #body="{ data }">
          <span class="mono">{{ data.planEndDate }}</span>
        </template>
      </Column>
      <Column :header="t('workPlanList.col.deliveryDate')" field="deliveryDate">
        <template #body="{ data }">
          <span class="mono">{{ data.deliveryDate }}</span>
        </template>
      </Column>
      <Column :header="t('workPlanList.col.sourceType')">
        <template #body="{ data }">
          <Tag
            :value="data.sourceType === 'FROM_WORK_ORDER' ? 'WO' : 'MPS'"
            :severity="data.sourceType === 'FROM_WORK_ORDER' ? 'success' : 'info'"
          />
        </template>
      </Column>
      <Column :header="t('workPlanList.col.riskType')">
        <template #body="{ data }">
          <RiskChip :risk="contextualRisk(data)" />
        </template>
      </Column>
    </DataTable>
  </div>
</template>

<style scoped>
.panel {
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  overflow: hidden;
}
.panel-head {
  padding: 12px 14px;
  border-bottom: 1px solid var(--p-content-border-color);
}
.panel-title {
  font-size: 14px;
  font-weight: 700;
}
.panel-sub {
  font-size: 11px;
  color: var(--p-text-muted-color);
  margin-top: 2px;
}
.ml-1 {
  margin-left: 4px;
}
</style>
