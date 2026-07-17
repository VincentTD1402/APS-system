<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import { MOCK_ITEMS, MOCK_ROUTINGS } from '@/mocks/master-data'
import { computed } from 'vue'

const { t, locale } = useI18n()

const rows = computed(() =>
  MOCK_ITEMS.map((i) => {
    const r = MOCK_ROUTINGS.find((x) => x.itemCode === i.code)
    return {
      ...i,
      wcCode: r?.wcCode ?? '',
      processNameKo: r?.processNameKo ?? '',
      processNameVi: r?.processNameVi ?? '',
      standardStMin: r?.standardStMin ?? 0,
    }
  })
)
</script>

<template>
  <div class="page">
    <h2>{{ t('nav.items') }}</h2>
    <DataTable :value="rows" data-key="code" size="small" striped-rows>
      <Column :header="t('master.item.code')" field="code" class="mono" />
      <Column :header="t('master.item.name')">
        <template #body="{ data }">{{ locale === 'ko' ? data.nameKo : data.nameVi }}</template>
      </Column>
      <Column :header="t('master.item.uom')" field="uom" class="mono" />
      <Column :header="t('master.routing.wc')" field="wcCode" class="mono" />
      <Column :header="t('master.routing.process')">
        <template #body="{ data }">{{ locale === 'ko' ? data.processNameKo : data.processNameVi }}</template>
      </Column>
      <Column :header="t('master.routing.standardSt')" field="standardStMin" class="mono" />
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
