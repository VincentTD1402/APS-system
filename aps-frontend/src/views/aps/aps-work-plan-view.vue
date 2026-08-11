<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, type ComponentPublicInstance } from 'vue'
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
  data: { dateStart?: string; dateEnd?: string; memo?: string; reqQty?: number }
}) {
  if (!selectedRow.value) return
  store.stageConfirm({
    rowKey: payload.rowKey,
    orderId: selectedRow.value.id,
    mode: payload.mode,
    data: payload.data,
  })
  showToast('저장되었습니다 · 시뮬레이션 대기')
}

function onCancel() {
  // Form đã tự reset trong action-panel. Ngoài ra: nếu row đang có
  // pending adjustment hoặc đã 확인 → xoá để chip/badge trở về gốc.
  if (!selectedRow.value || !selectedKey.value) return
  const wasConfirmed = store.confirmedRows.has(selectedKey.value)
  store.cancelAdjustment(selectedRow.value.id, selectedKey.value)
  if (wasConfirmed) showToast('취소되었습니다')
}

// ── RUN APS button ─────────────────────────────────────────────────────────────
async function onRunAps() {
  try {
    await store.runAps()
  } catch {
    showToast('데이터 조회 실패 · 다시 시도해주세요')
  }
}

// ── 시뮬레이션 button ──────────────────────────────────────────────────────────
async function onSimulate() {
  try {
    await store.runSimulation()
  } catch {
    showToast('시뮬레이션 실패 · 다시 시도해주세요')
    return
  }
  // Selection sau simulation có thể trỏ tới data cũ — clear để user chọn lại
  selectedRow.value = null
  selectedKey.value = null
  store.selectRow(null)
  showToast('시뮬레이션 완료 · 스케줄 재계산됨')
}

// ── 작업지시 생성 button ───────────────────────────────────────────────────────
const canDispatch = computed(() => {
  if (!selectedKey.value || !selectedRow.value) return false
  // Chỉ cho dispatch khi row ở state 'solved' (đã simulate xong + risk hết).
  if (store.badgeStateOf(selectedRow.value, selectedKey.value) !== 'solved') return false
  if (store.dispatchedIds.has(selectedKey.value)) return false
  return true
})

function onDispatch() {
  if (!selectedKey.value || !canDispatch.value) return
  store.dispatchWorkOrder(selectedKey.value)
  showToast('작업지시가 생성되었습니다')
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

onMounted(() => {
  // Auto-run APS lần đầu để panels hiện data ngay khi vào trang.
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
  <main class="aps-canvas" aria-label="APS 작업계획 대시보드">
    <Toast :message="toastMessage" :visible="toastVisible" />

    <h1 class="aps-title">APS 작업계획</h1>

    <div class="filter-row">
      <FilterBar />
      <button
        class="btn-run-aps"
        type="button"
        aria-label="데이터 불러오기"
        :disabled="store.isRunning"
        @click="onRunAps"
      >
        <span v-if="store.isRunning">불러오는 중…</span>
        <template v-else>▶ 데이터 불러오기</template>
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
            :disabled="store.pendingCount === 0 || store.isSimulating"
            :class="{ 'is-disabled': store.pendingCount === 0 || store.isSimulating }"
            @click="onSimulate"
          >
            시뮬레이션
            <span class="btn-badge">{{ store.pendingCount }}</span>
          </button>
          <button
            class="btn-wo"
            type="button"
            :disabled="!canDispatch"
            @click="onDispatch"
          >
            작업지시 생성
          </button>
        </div>
      </div>
    </div>
  </main>
</template>
