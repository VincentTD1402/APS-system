<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import { MOCK_MPS } from '@/mocks/mps-data'

const { t } = useI18n()
</script>

<template>
  <div class="page">
    <h2>{{ t('mps.list') }}</h2>
    <DataTable :value="MOCK_MPS" data-key="id" size="small" striped-rows>
      <Column :header="t('mps.orderNo')" field="orderNo" class="mono" />
      <Column :header="t('master.item.code')" field="itemCode" class="mono" />
      <Column :header="t('workPlanList.col.planQty')">
        <template #body="{ data }">
          <span class="mono">{{ data.planQty.toLocaleString() }}</span>
        </template>
      </Column>
      <Column :header="t('mps.endDate')" field="endDate" class="mono" />
      <Column :header="t('workPlanList.col.planStart')" field="workStartDate" class="mono" />
      <Column :header="t('workPlanList.col.planEnd')" field="workEndDate" class="mono" />
      <Column :header="t('mps.status')">
        <template #body="{ data }">
          <Tag :value="data.status === 'DRAFT' ? t('mps.statusDraft') : data.status" severity="info" />
        </template>
      </Column>
    </DataTable>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
h2 {
  margin: 0;
}
</style>
