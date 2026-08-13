<script setup lang="ts">
import { ref, onMounted, onUnmounted, type ComponentPublicInstance } from 'vue'
import { useI18n } from 'vue-i18n'
import { useApsStore } from '@/stores/aps-store'
import { useMasterStore } from '@/stores/master-store'
import FilterBar from '@/components/aps/filter-bar.vue'
import KpiRow from '@/components/aps/kpi-row.vue'
import LoadMatrix from '@/components/aps/load-matrix.vue'
import WorkPlanList from '@/components/aps/work-plan-list.vue'
import AiPanel from '@/components/aps/ai-panel.vue'
import ActionPanel from '@/components/aps/action-panel.vue'
import Toast from '@/components/aps/toast.vue'
import type { WorkPlanRow } from '@/data/mock-scheduler'

const store = useApsStore()
const masterStore = useMasterStore()
const { t } = useI18n()

// ── Toast ─────────────────────────────────────────────────────────────────────
const toastMessage = ref('')
const toastVisible = ref(false)
let toastTimer: ReturnType<typeof setTimeout> | null = null

function showToast(msg: string) {
  if (toastTimer) clearTimeout(toastTimer)
  toastMessage.value = msg
  toastVisible.value = true
  toastTimer = setTimeout(() => { toastVisible.value = false }, 1800)
}

// ── Selected row (lifted from work-plan-list) ─────────────────────────────────
const selectedRow = ref<WorkPlanRow | null>(null)
const selectedKey = ref<string | null>(null)

function onWpSelect(row: WorkPlanRow, key: string) {
  selectedRow.value = row
  selectedKey.value = key
}

// ── Action panel handlers ─────────────────────────────────────────────────────
function onConfirm(payload: {
  rowKey: string
  mode: string
  data: { dateStart?: string; dateEnd?: string; memo?: string; reqQty?: number; itemNo?: string }
}) {
  if (!selectedRow.value) return
  store.stageConfirm({
    rowKey: payload.rowKey,
    orderId: selectedRow.value.id,
    mode: payload.mode,
    data: payload.data,
  })
  showToast(t('apsView.toastConfirmSaved'))
}

function onCancel() {
  // Form đã tự reset trong action-panel. Ngoài ra: nếu row đang có
  // pending adjustment hoặc đã 확인 → xoá để chip/badge trở về gốc.
  if (!selectedRow.value || !selectedKey.value) return
  const wasConfirmed = store.confirmedRows.has(selectedKey.value)
  store.cancelAdjustment(selectedRow.value.id, selectedKey.value)
  if (wasConfirmed) showToast(t('apsView.toastCancelled'))
}

// ── RUN APS button ─────────────────────────────────────────────────────────────
async function onRunAps() {
  try {
    await store.runAps()
  } catch {
    showToast(t('apsView.toastRunFailed'))
  }
}

// ── 시뮬레이션 button ──────────────────────────────────────────────────────────
async function onSimulate() {
  if (!store.hasData) {
    showToast(t('apsView.toastNeedRun'))
    return
  }
  let purchaseRequestFailed = false
  try {
    ;({ purchaseRequestFailed } = await store.runSimulation())
  } catch {
    showToast(t('apsView.toastSimFailed'))
    return
  }
  // Selection sau simulation có thể trỏ tới data cũ — clear để user chọn lại
  selectedRow.value = null
  selectedKey.value = null
  store.selectRow(null)
  showToast(purchaseRequestFailed ? t('apsView.toastSimPrFailed') : t('apsView.toastSimDone'))
}

// ── 작업지시 생성 button ───────────────────────────────────────────────────────
// Nút luôn enable — chỉ chặn bấm trùng lúc đang gọi API (isDispatching), không
// gate theo business state nữa. Thiếu selection / đã dispatch rồi thì báo toast.
async function onDispatch() {
  if (!selectedKey.value || !selectedRow.value) {
    showToast(t('apsView.toastNeedSelect'))
    return
  }
  if (store.dispatchedIds.has(selectedKey.value)) {
    showToast(t('apsView.toastAlreadyDispatched'))
    return
  }
  try {
    const { pushed } = await store.dispatchWorkOrder(selectedRow.value.id, selectedKey.value)
    showToast(pushed ? t('apsView.toastDispatchDone') : t('apsView.toastDispatchFailed'))
  } catch {
    showToast(t('apsView.toastDispatchError'))
  }
}

// ── Height sync (KPI + LoadMatrix → AiPanel) ──────────────────────────────────
const kpiCmp = ref<ComponentPublicInstance | null>(null)
const lmCmp  = ref<ComponentPublicInstance | null>(null)
const aiCmp  = ref<ComponentPublicInstance | null>(null)
const ROW_GAP = 11

let ro: ResizeObserver | null = null

function syncAiHeight() {
  const kpiEl = kpiCmp.value?.$el as HTMLElement | undefined
  const lmEl  = lmCmp.value?.$el as HTMLElement | undefined
  const aiEl  = aiCmp.value?.$el as HTMLElement | undefined
  if (!kpiEl || !lmEl || !aiEl) return
  const kpiH = kpiEl.getBoundingClientRect().height
  const lmH  = lmEl.getBoundingClientRect().height
  aiEl.style.height = `${kpiH + ROW_GAP + lmH}px`
}

onMounted(async () => {
  // Load master data (workCenters/items/routings/bom/inventory) trước — load-matrix
  // render rows từ workCenters. Nếu không load, matrix rỗng.
  await masterStore.ensureLoaded()
  // Auto-run APS để panels hiện data ngay khi vào trang.
  // User vẫn có thể bấm RUN APS để refresh sau đó.
  store.runAps()

  syncAiHeight()
  requestAnimationFrame(syncAiHeight)
  setTimeout(syncAiHeight, 100)
  setTimeout(syncAiHeight, 500)

  window.addEventListener('resize', syncAiHeight)

  if (window.ResizeObserver) {
    ro = new ResizeObserver(syncAiHeight)
    const kpiEl = kpiCmp.value?.$el as HTMLElement | undefined
    const lmEl  = lmCmp.value?.$el as HTMLElement | undefined
    if (kpiEl) ro.observe(kpiEl)
    if (lmEl)  ro.observe(lmEl)
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', syncAiHeight)
  ro?.disconnect()
  if (toastTimer) clearTimeout(toastTimer)
})
</script>

<template>
  <main class="aps-canvas" :aria-label="t('nav.aps')">
    <Toast :message="toastMessage" :visible="toastVisible" />

    <h1 class="aps-title">{{ t('nav.aps') }}</h1>

    <div class="filter-row">
      <FilterBar />
      <button
        class="btn-run-aps"
        type="button"
        :aria-label="t('apsView.runIdle')"
        :disabled="store.isRunning"
        @click="onRunAps"
      >
        <span v-if="store.isRunning">{{ t('apsView.runLoading') }}</span>
        <template v-else>{{ t('apsView.runIdle') }}</template>
      </button>
    </div>

    <div class="content-grid">
      <div class="col-left">
        <KpiRow ref="kpiCmp" />
        <LoadMatrix ref="lmCmp" />
        <WorkPlanList @select="onWpSelect" />
      </div>

      <div class="col-right">
        <AiPanel ref="aiCmp" />
        <ActionPanel
          :row="selectedRow"
          :row-key="selectedKey"
          @confirm="onConfirm"
          @cancel="onCancel"
        />
        <div class="action-btn-row">
          <button
            class="btn-sim"
            type="button"
            :disabled="store.isSimulating"
            @click="onSimulate"
          >
            {{ store.isSimulating ? t('apsView.simLoading') : t('apsView.simIdle') }}
            <span class="btn-badge">{{ store.pendingCount }}</span>
          </button>
          <button
            class="btn-wo"
            type="button"
            :disabled="store.isDispatching"
            @click="onDispatch"
          >
            {{ store.isDispatching ? t('apsView.dispatchLoading') : t('detail.createWorkOrder') }}
          </button>
        </div>
      </div>
    </div>
  </main>
</template>
