<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import { useMasterStore } from '@/stores/master-store'
import { ref, onMounted } from 'vue'

const { t, locale } = useI18n()
const master = useMasterStore()

onMounted(() => master.ensureLoaded())

const expandedRows = ref({})
</script>

<template>
  <div class="page">
    <h2>{{ t('nav.workCenters') }}</h2>
    <DataTable
      v-model:expanded-rows="expandedRows"
      :value="master.workCenters"
      data-key="code"
      striped-rows
      size="small"
      :loading="master.loading"
    >
      <Column expander style="width: 3rem" />
      <Column :header="t('master.wc.code')" field="code" class="mono" />
      <Column :header="t('master.wc.name')">
        <template #body="{ data }">
          {{ locale === 'ko' ? data.nameKo : data.nameVi || data.nameKo }}
        </template>
      </Column>
      <Column :header="t('master.wc.defaultRuntime')" field="defaultRuntimeMin" class="mono" />
      <Column :header="t('master.wc.equipmentCount')">
        <template #body="{ data }">
          <span class="mono">{{ data.equipments.length }}</span>
        </template>
      </Column>
      <Column :header="t('master.wc.totalRuntime')">
        <template #body="{ data }">
          <span class="mono" style="font-weight: 700">{{ data.totalRuntimeMin }}</span>
        </template>
      </Column>
      <template #expansion="{ data }">
        <div class="eq-wrap">
          <h4>{{ t('master.equipment.code') }}</h4>
          <DataTable :value="data.equipments" size="small">
            <Column :header="t('master.equipment.code')" field="code" class="mono" />
            <Column :header="t('master.wc.name')">
              <template #body="{ data: eq }">
                {{ locale === 'ko' ? eq.nameKo : eq.nameVi || eq.nameKo }}
              </template>
            </Column>
            <Column :header="t('master.equipment.stRate')" field="stRate" class="mono" />
            <Column :header="t('master.equipment.runtime')">
              <template #body="{ data: eq }">
                <span class="mono">{{ Math.round(data.defaultRuntimeMin * eq.stRate) }}</span>
              </template>
            </Column>
          </DataTable>
        </div>
      </template>
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
.eq-wrap {
  padding: 8px 24px;
  background: var(--p-content-hover-background);
}
</style>
