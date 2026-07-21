<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import { useMasterStore } from '@/stores/master-store'
import { computed, onMounted } from 'vue'

const { t, locale } = useI18n()
const master = useMasterStore()

onMounted(() => master.ensureLoaded())

// Enrich item với routing step đầu (item-level lookup — 1 item nhiều routing thì lấy row đầu).
const rows = computed(() =>
  master.items.map((i) => {
    const r = master.routings.find((x) => x.itemCode === i.code)
    return {
      ...i,
      wcCode: r?.wcCode ?? '',
      processNameKo: r?.processNameKo ?? '',
      processNameVi: r?.processNameVi ?? null,
      standardStMin: r?.standardStMin ?? 0,
    }
  })
)
</script>

<template>
  <div class="page">
    <h2>{{ t('nav.items') }}</h2>
    <DataTable :value="rows" data-key="code" size="small" striped-rows :loading="master.loading">
      <Column :header="t('master.item.code')" field="code" class="mono" />
      <Column :header="t('master.item.name')">
        <template #body="{ data }">{{ locale === 'ko' ? data.nameKo : data.nameVi || data.nameKo }}</template>
      </Column>
      <Column :header="t('master.item.uom')" field="uom" class="mono" />
      <Column :header="t('master.routing.wc')" field="wcCode" class="mono" />
      <Column :header="t('master.routing.process')">
        <template #body="{ data }">{{ locale === 'ko' ? data.processNameKo : data.processNameVi || data.processNameKo }}</template>
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
