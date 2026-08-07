<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { ref, watch } from 'vue'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import InputNumber from 'primevue/inputnumber'
import Textarea from 'primevue/textarea'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import type { WorkPlan } from '@/types/planning'
import { fetchMaterialShortageByParent } from '@/api/master'

export interface PurchaseLineDraft {
  itemNo: string
  itemName: string | null
  shortageQty: number
  onHandQty: number
  qty: number
}

const props = defineProps<{ visible: boolean; plan: WorkPlan | null }>()
const emit = defineEmits<{
  'update:visible': [value: boolean]
  submit: [payload: { note: string; lines: PurchaseLineDraft[] }]
}>()

const { t } = useI18n()
const note = ref('')
const lines = ref<PurchaseLineDraft[]>([])
const loading = ref(false)

// The plan's own item (product/semi-product) is NOT what gets purchased —
// its BOM raw-material components are. One product can need several.
watch(
  () => props.plan,
  async (p) => {
    note.value = ''
    lines.value = []
    if (!p) return
    loading.value = true
    try {
      const rows = await fetchMaterialShortageByParent(p.itemCode)
      lines.value = rows
        .filter((r) => r.isShort)
        .map((r) => ({
          itemNo: r.itemNo ?? '',
          itemName: r.itemName,
          shortageQty: r.shortageQty,
          onHandQty: r.availableQty,
          qty: r.shortageQty,
        }))
    } finally {
      loading.value = false
    }
  }
)

function onCancel(): void {
  emit('update:visible', false)
}

function onSubmit(): void {
  const submitted = lines.value.filter((l) => l.qty > 0)
  if (submitted.length === 0) return
  emit('submit', { note: note.value, lines: submitted })
  emit('update:visible', false)
}
</script>

<template>
  <Dialog
    :visible="visible"
    modal
    :header="t('dialog.purchase.title')"
    :style="{ width: '620px' }"
    @update:visible="emit('update:visible', $event)"
  >
    <div class="body">
      <div class="row">
        <label>{{ t('detail.info.item') }}</label>
        <div class="mono">{{ plan?.itemCode }}</div>
      </div>

      <DataTable :value="lines" :loading="loading" size="small" data-key="itemNo">
        <Column :header="t('master.item.code')" field="itemNo" class="mono" />
        <Column :header="t('master.item.name')" field="itemName" />
        <Column :header="t('dialog.purchase.shortageQty')">
          <template #body="{ data }">
            <span class="mono">{{ data.shortageQty.toLocaleString() }}</span>
          </template>
        </Column>
        <Column :header="t('dialog.purchase.onHandQty')">
          <template #body="{ data }">
            <span class="mono">{{ data.onHandQty.toLocaleString() }}</span>
          </template>
        </Column>
        <Column :header="t('dialog.purchase.requestQty')">
          <template #body="{ data }">
            <InputNumber v-model="data.qty" :min="0" show-buttons size="small" />
          </template>
        </Column>
      </DataTable>
      <div v-if="!loading && lines.length === 0" class="empty">
        {{ t('dialog.purchase.noShortage') }}
      </div>

      <div class="row">
        <label>{{ t('dialog.purchase.note') }}</label>
        <Textarea v-model="note" rows="3" />
      </div>
    </div>
    <template #footer>
      <Button :label="t('common.cancel')" severity="secondary" text @click="onCancel" />
      <Button
        :label="t('common.confirm')"
        icon="pi pi-check"
        :disabled="lines.filter((l) => l.qty > 0).length === 0"
        @click="onSubmit"
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
.row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.row label {
  font-size: 11px;
  font-weight: 600;
  color: var(--p-text-muted-color);
}
.empty {
  text-align: center;
  padding: 12px;
  font-size: 12px;
  color: var(--p-text-muted-color);
}
</style>
