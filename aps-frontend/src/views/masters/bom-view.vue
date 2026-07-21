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
    <h2>{{ t('nav.bom') }}</h2>
    <DataTable :value="master.bom" data-key="id" size="small" striped-rows :loading="master.loading">
      <Column :header="t('master.bom.parent')" field="parentItemCode" class="mono" />
      <Column :header="t('master.bom.child')" field="childItemCode" class="mono" />
      <Column :header="t('master.bom.qtyPer')" field="qtyPer" class="mono" />
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
