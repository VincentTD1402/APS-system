<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useApsStore } from '@/stores/aps-store'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import RiskChip from './risk-chip.vue'
import PurchaseRequestDialog, { type PurchaseLineDraft } from './dialogs/purchase-request-dialog.vue'
import ScheduleAdjustDialog from './dialogs/schedule-adjust-dialog.vue'
import { computed, ref } from 'vue'
import { useToast } from 'primevue/usetoast'

const { t, locale } = useI18n()
const store = useApsStore()
const toast = useToast()

const plan = computed(() => store.selectedPlan)

const canRequestPurchase = computed(
  () => plan.value?.riskType === 'MATERIAL_SHORT' || plan.value?.riskType === 'MATERIAL_AND_OVERLOAD'
)
const canAdjust = computed(
  () => plan.value?.riskType === 'OVERLOAD' || plan.value?.riskType === 'MATERIAL_AND_OVERLOAD'
)

const purchaseDialog = ref(false)
const adjustDialog = ref(false)

function onPurchaseSubmit(payload: { note: string; lines: PurchaseLineDraft[] }): void {
  if (!plan.value) return
  store.stagePurchaseRequest(
    plan.value.id,
    payload.note,
    payload.lines.map((l) => ({ itemNo: l.itemNo, itemName: l.itemName, qty: l.qty }))
  )
  toast.add({
    severity: 'info',
    summary: t('dialog.purchase.title'),
    detail: t('dialog.purchase.stagedNote'),
    life: 4000,
  })
}

function onAdjustSubmit(payload: { newStart: string; newEnd: string }): void {
  if (!plan.value) return
  store.stageAdjustment(plan.value.id, payload.newStart, payload.newEnd)
  toast.add({
    severity: 'warn',
    summary: t('dialog.adjust.title'),
    detail: t('dialog.adjust.note'),
    life: 4000,
  })
}

</script>

<template>
  <div class="panel detail">
    <div class="panel-head">
      <div class="panel-title">{{ t('detail.title') }}</div>
      <Tag v-if="plan" :value="plan.wcName || plan.wcCode" severity="secondary" />
    </div>
    <div v-if="!plan" class="empty">
      <i class="pi pi-hand-pointer" style="font-size: 24px; color: var(--p-text-muted-color)" />
      <div>{{ t('detail.selectPlan') }}</div>
    </div>
    <div v-else class="body">
      <div class="header-row">
        <div class="tmp-no mono">{{ plan.tmpPlanNo }}</div>
        <RiskChip :risk="plan.riskType" />
      </div>
      <Tag
        v-if="store.selectedPendingPurchase"
        :value="`${t('detail.purchaseRequest')}: ${store.selectedPendingPurchase.lines.length}`"
        severity="info"
        icon="pi pi-shopping-cart"
        class="adj-badge"
      />
      <Tag
        v-if="store.selectedPending"
        :value="`Pending: ${store.selectedPending.newStart} → ${store.selectedPending.newEnd}`"
        severity="info"
        icon="pi pi-clock"
        class="adj-badge"
      />
      <Tag
        v-else-if="plan.adjusted"
        :value="t('detail.adjustedBadge')"
        severity="warn"
        icon="pi pi-check"
        class="adj-badge"
      />

      <div class="info-grid">
        <div class="info-item">
          <div class="label">{{ t('detail.info.item') }}</div>
          <div class="value">{{ locale === 'ko' ? plan.itemNameKo : plan.itemNameVi }}</div>
        </div>
        <div class="info-item">
          <div class="label">{{ t('detail.info.wc') }}</div>
          <div class="value mono">{{ plan.wcName || plan.wcCode }}</div>
        </div>
        <div class="info-item">
          <div class="label">{{ t('detail.info.planQty') }}</div>
          <div class="value mono">{{ plan.planQty.toLocaleString() }}</div>
        </div>
        <div class="info-item">
          <div class="label">{{ t('detail.info.delivery') }}</div>
          <div class="value mono">{{ plan.deliveryDate }}</div>
        </div>
        <div class="info-item">
          <div class="label">{{ t('detail.info.start') }}</div>
          <div class="value mono">{{ plan.planStartDate }}</div>
        </div>
        <div class="info-item">
          <div class="label">{{ t('detail.info.end') }}</div>
          <div class="value mono">{{ plan.planEndDate }}</div>
        </div>
        <div class="info-item full">
          <div class="label">{{ t('detail.info.source') }}</div>
          <div class="value mono">
            {{ plan.sourceType === 'FROM_WORK_ORDER' ? t('detail.source.workOrder') : t('detail.source.mps') }} ·
            {{ plan.orderNo }}
          </div>
        </div>
        <div v-if="plan.shortageQty > 0" class="info-item full shortage">
          <div class="label">{{ t('dialog.purchase.shortageQty') }}</div>
          <div class="value mono">{{ plan.shortageQty.toLocaleString() }}</div>
        </div>
      </div>

      <div class="actions">
        <div v-if="canRequestPurchase" class="action-row">
          <Button
            :label="store.selectedPendingPurchase ? t('detail.purchaseRequestDone') : t('detail.purchaseRequest')"
            :icon="store.selectedPendingPurchase ? 'pi pi-check' : 'pi pi-shopping-cart'"
            :severity="store.selectedPendingPurchase ? 'success' : 'info'"
            :disabled="!!store.selectedPendingPurchase"
            class="action-btn"
            @click="purchaseDialog = true"
          />
          <Button
            v-if="store.selectedPendingPurchase"
            icon="pi pi-times"
            severity="danger"
            text
            :aria-label="t('detail.cancelPurchaseRequest')"
            :title="t('detail.cancelPurchaseRequest')"
            @click="store.discardPurchaseRequest(plan!.id)"
          />
        </div>
        <div v-if="canAdjust" class="action-row">
          <Button
            :label="store.selectedPending ? t('detail.scheduleAdjustDone') : t('detail.scheduleAdjust')"
            :icon="store.selectedPending ? 'pi pi-check' : 'pi pi-calendar-plus'"
            :severity="store.selectedPending ? 'success' : 'warn'"
            :disabled="!!store.selectedPending"
            class="action-btn"
            @click="adjustDialog = true"
          />
          <Button
            v-if="store.selectedPending"
            icon="pi pi-times"
            severity="danger"
            text
            :aria-label="t('detail.cancelScheduleAdjust')"
            :title="t('detail.cancelScheduleAdjust')"
            @click="store.discardPending(plan!.id)"
          />
        </div>
      </div>
    </div>

    <PurchaseRequestDialog v-model:visible="purchaseDialog" :plan="plan" @submit="onPurchaseSubmit" />
    <ScheduleAdjustDialog v-model:visible="adjustDialog" :plan="plan" @submit="onAdjustSubmit" />
  </div>
</template>

<style scoped>
.panel {
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  overflow: hidden;
  height: 100%;
  display: flex;
  flex-direction: column;
}
.panel-head {
  padding: 12px 14px;
  border-bottom: 1px solid var(--p-content-border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.panel-title {
  font-size: 14px;
  font-weight: 700;
}
.empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
  justify-content: center;
  color: var(--p-text-muted-color);
  font-size: 12px;
}
.body {
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  flex: 1;
}
.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.tmp-no {
  font-size: 14px;
  font-weight: 700;
}
.adj-badge {
  align-self: flex-start;
}
.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  padding: 10px;
  background: var(--p-content-hover-background);
  border-radius: 6px;
}
.info-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.info-item.full {
  grid-column: span 2;
}
.info-item.shortage .value {
  color: var(--aps-crit);
  font-weight: 700;
}
.label {
  font-size: 10.5px;
  font-weight: 600;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
.value {
  font-size: 13px;
  font-weight: 600;
}
.actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 4px;
}
.action-row {
  display: flex;
  align-items: center;
  gap: 4px;
}
.action-btn {
  flex: 1;
}
</style>
