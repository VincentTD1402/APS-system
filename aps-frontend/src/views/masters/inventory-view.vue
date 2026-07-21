<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import { useMasterStore } from '@/stores/master-store'
import { onMounted } from 'vue'

const { t } = useI18n()
const master = useMasterStore()

onMounted(() => master.ensureLoaded())
</script>

<template>
  <div class="page">
    <h2>{{ t('nav.inventory') }}</h2>
    <DataTable :value="master.inventory" data-key="id" size="small" striped-rows :loading="master.loading">
      <Column :header="t('master.item.code')" field="itemCode" class="mono" />
      <Column :header="t('master.inventory.warehouse')" field="warehouseCode" class="mono" />
      <Column :header="t('master.inventory.onHand')" field="onHand" class="mono" />
      <Column :header="t('master.inventory.asOf')" field="asOfDate" class="mono" />
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
