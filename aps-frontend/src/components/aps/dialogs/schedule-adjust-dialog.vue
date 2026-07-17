<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { ref, watch } from 'vue'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import DatePicker from 'primevue/datepicker'
import Message from 'primevue/message'
import type { WorkPlan } from '@/types/planning'

const props = defineProps<{ visible: boolean; plan: WorkPlan | null }>()
const emit = defineEmits<{
  'update:visible': [value: boolean]
  submit: [payload: { newStart: string; newEnd: string }]
}>()

const { t } = useI18n()
const newStart = ref<Date | null>(null)
const newEnd = ref<Date | null>(null)

watch(
  () => props.plan,
  (p) => {
    newStart.value = p ? new Date(p.planStartDate) : null
    newEnd.value = p ? new Date(p.planEndDate) : null
  }
)

function fmt(d: Date | null): string {
  if (!d) return ''
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function onCancel(): void {
  emit('update:visible', false)
}

function onSubmit(): void {
  if (!newStart.value || !newEnd.value) return
  emit('submit', { newStart: fmt(newStart.value), newEnd: fmt(newEnd.value) })
  emit('update:visible', false)
}
</script>

<template>
  <Dialog
    :visible="visible"
    modal
    :header="t('dialog.adjust.title')"
    :style="{ width: '420px' }"
    @update:visible="emit('update:visible', $event)"
  >
    <div class="body">
      <div class="row">
        <label>{{ t('detail.info.item') }}</label>
        <div class="mono">{{ plan?.itemCode }} · {{ plan?.wcCode }}</div>
      </div>
      <div class="row">
        <label>{{ t('dialog.adjust.newStart') }}</label>
        <DatePicker v-model="newStart" date-format="yy-mm-dd" show-icon />
      </div>
      <div class="row">
        <label>{{ t('dialog.adjust.newEnd') }}</label>
        <DatePicker v-model="newEnd" date-format="yy-mm-dd" show-icon />
      </div>
      <Message severity="warn" :closable="false">{{ t('dialog.adjust.note') }}</Message>
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
