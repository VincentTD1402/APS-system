<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useApsStore } from '@/stores/aps-store'
import BadgeTag from '@/components/aps/badge-tag.vue'
import type { WorkPlanRow, RiskKind } from '@/data/mock-scheduler'

interface Props {
  row?: WorkPlanRow | null
  rowKey?: string | null
}
const props = withDefaults(defineProps<Props>(), { row: null, rowKey: null })

const emit = defineEmits<{
  confirm: [payload: {
    rowKey: string
    mode: string
    data: { dateStart?: string; dateEnd?: string; memo?: string; reqQty?: number }
  }]
  cancel: []
}>()

const store = useApsStore()

// Mode logic:
// - riskTypes (từ scheduler) là **day-based** — chip có thể là material_short do
//   plan chạm ngày shortage của plan khác, NHƯNG bản thân plan không có NVL cần đặt.
// - Vì vậy chỉ mở form 구매요청/both khi plan CÓ BOM shortage thực sự
//   (row.shortages.length > 0). Còn lại chỉ mở adjust để đổi lịch.
type Mode = 'adjust' | 'shortage' | 'both'
const mode = computed<Mode>(() => {
  const rt: RiskKind[] = props.row?.riskTypes ?? []
  const hasOwnShortage = (props.row?.shortages ?? []).length > 0
  const over = rt.includes('overload')
  if (over && hasOwnShortage) return 'both'
  if (hasOwnShortage) return 'shortage'
  return 'adjust'
})

const titleLabel = computed(() => {
  if (mode.value === 'shortage') return '구매요청'
  if (mode.value === 'both')     return '일정조정+구매요청'
  return '일정조정'
})

// Chip meta cho row hiện tại
interface Chip { code: string; label: string }
const rowChip = computed<Chip>(() => {
  const rt = props.row?.riskTypes ?? []
  const hasOver = rt.includes('overload')
  const hasShort = rt.includes('material_short')
  if (hasOver && hasShort) return { code: 'both', label: '자재부족+부하초과' }
  if (hasOver) return { code: 'overload', label: '부하초과' }
  if (hasShort) return { code: 'shortage', label: '자재부족' }
  return { code: 'normal', label: '정상' }
})

// Material info lấy từ row.shortages — dòng NVL thực sự thiếu.
// Nếu row không có shortage nào, dùng placeholder rỗng (chỉ vào panel shortage/both
// khi riskTypes có material_short → shortages luôn ≥ 1 phần tử).
interface MatInfo { materialName: string; onHand: number; shortage: number }
const materialInfo = computed<MatInfo>(() => {
  const r = props.row
  if (!r || r.shortages.length === 0) return { materialName: '-', onHand: 0, shortage: 0 }
  const first = r.shortages[0]
  return {
    materialName: first.materialCode,
    onHand: first.availableQty,       // stock còn khi tới lượt plan này (không phải tổng kho)
    shortage: Math.round(first.shortageQty),
  }
})

// --- Editable state -----------------------------------------------------------
const dateStart = ref('')
const dateEnd   = ref('')
const memo      = ref('')
const reqQty    = ref<number>(0)

// Reset khi đổi row
watch(
  () => props.row,
  (r) => {
    if (!r) return
    if (mode.value === 'adjust' || mode.value === 'both') {
      dateStart.value = r.planStart
      dateEnd.value   = r.deliveryDate
      memo.value      = ''
    }
    if (mode.value === 'shortage' || mode.value === 'both') {
      reqQty.value = materialInfo.value.shortage
    }
  },
  { immediate: true },
)

function onConfirm() {
  if (!props.rowKey) return
  const data =
    mode.value === 'adjust'   ? { dateStart: dateStart.value, dateEnd: dateEnd.value, memo: memo.value } :
    mode.value === 'shortage' ? { reqQty: reqQty.value } :
    { dateStart: dateStart.value, dateEnd: dateEnd.value, memo: memo.value, reqQty: reqQty.value }

  emit('confirm', { rowKey: props.rowKey, mode: mode.value, data })
}

function onCancel() {
  if (props.row) {
    if (mode.value === 'adjust' || mode.value === 'both') {
      dateStart.value = props.row.planStart
      dateEnd.value   = props.row.deliveryDate
      memo.value      = ''
    }
    if (mode.value === 'shortage' || mode.value === 'both') {
      reqQty.value = materialInfo.value.shortage
    }
  }
  emit('cancel')
}

const badgeState = computed(() =>
  props.row && props.rowKey ? store.badgeStateOf(props.row, props.rowKey) : null
)
</script>

<template>
  <div class="action-panel area-action">
    <div class="action-header">
      <svg class="ic-tool" aria-hidden="true"><use href="#ic-tool"/></svg>
      Action [{{ titleLabel }}]
      <BadgeTag :state="badgeState" />
    </div>

    <div class="action-body">
      <div v-if="!row" class="action-empty">행을 선택하세요</div>

      <!-- Mode: 일정조정 -->
      <div v-else-if="mode === 'adjust'" class="action-content">
        <span class="act-label">작업지시번호 :</span>
        <span class="act-value">{{ row.workOrderNo ?? row.tmpPlanNo ?? '-' }}</span>
        <span :class="`risk-chip r-${rowChip.code}`">{{ rowChip.label }}</span>

        <span class="act-label">품목 :</span>
        <span class="act-value">{{ row.itemName }}</span>
        <span></span>

        <span class="act-label">워크센터 :</span>
        <span class="act-value">{{ row.workcenterNo }}</span>
        <span></span>

        <span class="act-label">요청일 :</span>
        <span class="act-value act-range-inline">
          <input type="date" v-model="dateStart" class="act-inline-input" />
          <span class="act-sep">~</span>
          <input type="date" v-model="dateEnd" class="act-inline-input act-inline-input-end" />
        </span>
        <span></span>

        <span class="act-label act-label-top">메모 :</span>
        <span class="act-value act-memo-value">
          <textarea v-model="memo" placeholder="메모를 입력하세요" class="act-inline-textarea"></textarea>
        </span>
      </div>

      <!-- Mode: 일정조정 + 구매요청 (both) -->
      <div v-else-if="mode === 'both'" class="action-content">
        <span class="act-label">작업지시번호 :</span>
        <span class="act-value">{{ row.workOrderNo ?? row.tmpPlanNo ?? '-' }}</span>
        <span :class="`risk-chip r-${rowChip.code}`">{{ rowChip.label }}</span>

        <span class="act-label">품목 :</span>
        <span class="act-value">{{ row.itemName }}</span>
        <span></span>

        <span class="act-label">워크센터 :</span>
        <span class="act-value">{{ row.workcenterNo }}</span>
        <span></span>

        <span class="act-label">요청일 :</span>
        <span class="act-value act-range-inline">
          <input type="date" v-model="dateStart" class="act-inline-input" />
          <span class="act-sep">~</span>
          <input type="date" v-model="dateEnd" class="act-inline-input act-inline-input-end" />
        </span>
        <span></span>

        <span class="act-label">자재명 :</span>
        <span class="act-value">{{ materialInfo.materialName }}</span>
        <span></span>

        <span class="act-label">현재고 :</span>
        <span class="act-value">{{ materialInfo.onHand.toLocaleString('en-US') }}</span>
        <span></span>

        <span class="act-label">부족수량 :</span>
        <span class="act-value">{{ materialInfo.shortage.toLocaleString('en-US') }}</span>
        <span></span>

        <span class="act-label">요청수량 :</span>
        <span class="act-value">
          <input type="number" v-model.number="reqQty" class="act-inline-input act-inline-input-end" min="0" />
        </span>
        <span></span>

        <span class="act-label act-label-top">메모 :</span>
        <span class="act-value act-memo-value">
          <textarea v-model="memo" placeholder="메모를 입력하세요" class="act-inline-textarea"></textarea>
        </span>
      </div>

      <!-- Mode: 구매요청 (shortage) -->
      <div v-else class="action-content">
        <span class="act-label">품목 :</span>
        <span class="act-value">{{ row.itemName }}</span>
        <span :class="`risk-chip r-${rowChip.code}`">{{ rowChip.label }}</span>

        <span class="act-label">자재명 :</span>
        <span class="act-value">{{ materialInfo.materialName }}</span>
        <span></span>

        <span class="act-label">현재고 :</span>
        <span class="act-value">{{ materialInfo.onHand.toLocaleString('en-US') }}</span>
        <span></span>

        <span class="act-label">부족수량 :</span>
        <span class="act-value">{{ materialInfo.shortage.toLocaleString('en-US') }}</span>
        <span></span>

        <span class="act-label">요청수량 :</span>
        <span class="act-value">
          <input type="number" v-model.number="reqQty" class="act-inline-input act-inline-input-end" min="0" />
        </span>
        <span></span>
      </div>
    </div>

    <div class="action-footer">
      <button class="btn-cancel" type="button" @click="onCancel">✕ 취소</button>
      <button class="btn-confirm" type="button" :disabled="!row" @click="onConfirm">✓ 확인</button>
    </div>
  </div>
</template>

<style scoped>
.action-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 120px;
  color: #48494d;
  font-size: 13px;
}
</style>
