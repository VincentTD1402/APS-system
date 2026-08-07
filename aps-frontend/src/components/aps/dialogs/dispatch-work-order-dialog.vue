<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { computed, ref, watch } from 'vue'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Checkbox from 'primevue/checkbox'
import Tag from 'primevue/tag'
import { useConfirm } from 'primevue/useconfirm'
import { useApsStore } from '@/stores/aps-store'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{
  'update:visible': [value: boolean]
  confirm: [planIds: string[]]
}>()

const { t, locale } = useI18n()
const store = useApsStore()
const confirm = useConfirm()

const selected = ref<Set<string>>(new Set())

const plans = computed(() => store.filteredPlans)

watch(
  () => props.visible,
  (v) => {
    if (v) selected.value = new Set()
  }
)

const allSelected = computed(
  () => plans.value.length > 0 && plans.value.every((p) => selected.value.has(p.id))
)

function toggleAll(): void {
  selected.value = allSelected.value ? new Set() : new Set(plans.value.map((p) => p.id))
}

function toggleOne(id: string): void {
  const next = new Set(selected.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selected.value = next
}

function onCancel(): void {
  emit('update:visible', false)
}

function onConfirmClick(): void {
  if (selected.value.size === 0) return
  confirm.require({
    header: t('dialog.dispatch.confirmHeader'),
    message: t('dialog.dispatch.confirmMessage'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('common.confirm'),
    rejectLabel: t('common.cancel'),
    accept: () => {
      emit('confirm', Array.from(selected.value))
      emit('update:visible', false)
    },
  })
}
</script>

<template>
  <Dialog
    :visible="visible"
    modal
    :header="t('dialog.dispatch.title')"
    :style="{ width: '720px' }"
    @update:visible="emit('update:visible', $event)"
  >
    <div class="body">
      <DataTable :value="plans" size="small" scrollable scroll-height="400px" data-key="id">
        <Column style="width: 40px">
          <template #header>
            <Checkbox :model-value="allSelected" binary @update:model-value="toggleAll" />
          </template>
          <template #body="{ data }">
            <Checkbox :model-value="selected.has(data.id)" binary @update:model-value="() => toggleOne(data.id)" />
          </template>
        </Column>
        <Column :header="t('workPlanList.col.tmpPlanNo')" field="tmpPlanNo" class="mono">
          <template #body="{ data }">{{ data.tmpPlanNo ?? '—' }}</template>
        </Column>
        <Column :header="t('workPlanList.col.workOrderNo')" field="workOrderNo" class="mono">
          <template #body="{ data }">{{ data.workOrderNo ?? '—' }}</template>
        </Column>
        <Column style="width: 50px">
          <template #body="{ data }">
            <Tag v-if="store.pendingPurchaseRequests.has(data.id)" severity="info" value="po" />
          </template>
        </Column>
        <Column :header="t('workPlanList.col.item')">
          <template #body="{ data }">{{ locale === 'ko' ? data.itemNameKo : data.itemNameVi }}</template>
        </Column>
        <Column :header="t('workPlanList.col.wc')">
          <template #body="{ data }">{{ data.wcName ?? data.wcCode ?? '—' }}</template>
        </Column>
        <Column :header="t('workPlanList.col.planQty')">
          <template #body="{ data }">
            <span class="mono">{{ data.planQty.toLocaleString() }}</span>
          </template>
        </Column>
      </DataTable>
      <div v-if="plans.length === 0" class="empty">{{ t('dialog.dispatch.noPlans') }}</div>
    </div>
    <template #footer>
      <Button :label="t('common.cancel')" severity="secondary" text @click="onCancel" />
      <Button
        :label="`${t('common.confirm')} (${selected.size})`"
        icon="pi pi-check"
        :disabled="selected.size === 0"
        @click="onConfirmClick"
      />
    </template>
  </Dialog>
</template>

<style scoped>
.body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.empty {
  text-align: center;
  padding: 12px;
  font-size: 12px;
  color: var(--p-text-muted-color);
}
</style>
