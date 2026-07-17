<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { ref, watch } from 'vue'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import InputNumber from 'primevue/inputnumber'
import Textarea from 'primevue/textarea'
import type { WorkPlan } from '@/types/planning'

const props = defineProps<{ visible: boolean; plan: WorkPlan | null }>()
const emit = defineEmits<{
  'update:visible': [value: boolean]
  submit: [payload: { qty: number; note: string }]
}>()

const { t } = useI18n()
const qty = ref(0)
const note = ref('')

watch(
  () => props.plan,
  (p) => {
    qty.value = p?.shortageQty ?? 0
    note.value = ''
  }
)

function onCancel(): void {
  emit('update:visible', false)
}

function onSubmit(): void {
  emit('submit', { qty: qty.value, note: note.value })
  emit('update:visible', false)
}
</script>

<template>
  <Dialog
    :visible="visible"
    modal
    :header="t('dialog.purchase.title')"
    :style="{ width: '420px' }"
    @update:visible="emit('update:visible', $event)"
  >
    <div class="body">
      <div class="row">
        <label>{{ t('detail.info.item') }}</label>
        <div class="mono">{{ plan?.itemCode }}</div>
      </div>
      <div class="row">
        <label>{{ t('dialog.purchase.shortageQty') }}</label>
        <div class="mono">{{ plan?.shortageQty ?? 0 }}</div>
      </div>
      <div class="row">
        <label>{{ t('dialog.purchase.requestQty') }}</label>
        <InputNumber v-model="qty" :min="0" show-buttons />
      </div>
      <div class="row">
        <label>{{ t('dialog.purchase.note') }}</label>
        <Textarea v-model="note" rows="3" />
      </div>
    </div>
    <template #footer>
      <Button :label="t('common.cancel')" severity="secondary" text @click="onCancel" />
      <Button :label="t('common.confirm')" icon="pi pi-check" @click="onSubmit" />
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
</style>
