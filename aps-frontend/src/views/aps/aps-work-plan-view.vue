<script setup lang="ts">
import Toast from 'primevue/toast'
import SelectButton from 'primevue/selectbutton'
import FilterBar from '@/components/aps/filter-bar.vue'
import KpiRow from '@/components/aps/kpi-row.vue'
import LoadMatrix from '@/components/aps/load-matrix.vue'
import PlanDetailMatrix from '@/components/aps/plan-detail-matrix.vue'
import WorkPlanList from '@/components/aps/work-plan-list.vue'
import DetailPanel from '@/components/aps/detail-panel.vue'
import { useApsStore } from '@/stores/aps-store'
import { onMounted, ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const store = useApsStore()

type MatrixMode = 'aggregate' | 'detail'
const mode = ref<MatrixMode>('aggregate')
const modeOptions = computed(() => [
  { label: t('matrix.aggregate'), value: 'aggregate', icon: 'pi pi-th-large' },
  { label: t('matrix.detail'), value: 'detail', icon: 'pi pi-list' },
])

onMounted(async () => {
  if (!store.runId) await store.runAps()
})
</script>

<template>
  <Toast position="top-right" />
  <FilterBar />
  <KpiRow :kpi="store.kpi" />
  <div class="matrix-toolbar">
    <SelectButton v-model="mode" :options="modeOptions" option-label="label" option-value="value" size="small">
      <template #option="{ option }">
        <i :class="option.icon" style="margin-right: 6px" />
        {{ option.label }}
      </template>
    </SelectButton>
  </div>
  <div class="aps-grid">
    <div class="col-left">
      <LoadMatrix v-if="mode === 'aggregate'" />
      <PlanDetailMatrix v-else />
      <WorkPlanList />
    </div>
    <div class="col-right">
      <DetailPanel />
    </div>
  </div>
</template>

<style scoped>
.matrix-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 10px;
}
.aps-grid {
  display: grid;
  grid-template-columns: 1fr 400px;
  gap: 14px;
  align-items: start;
}
.col-left {
  display: flex;
  flex-direction: column;
  gap: 0;
  min-width: 0;
}
.col-right {
  position: sticky;
  top: 14px;
  max-height: calc(100vh - 100px);
}
@media (max-width: 1200px) {
  .aps-grid {
    grid-template-columns: 1fr;
  }
  .col-right {
    position: static;
    max-height: none;
  }
}
</style>
