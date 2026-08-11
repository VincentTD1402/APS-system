// Pinia store — RUN/시뮬레이션 gọi thẳng BE (`POST /aps/run`, `POST /aps/adjust`).
// Contract khớp `aps-backend/app/schemas/aps.py::ApsRunResult`.
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  enumerateDates,
  type LoadCellOut, type WorkPlanRow, type Kpi,
} from '@/data/mock-scheduler'
import { useMasterStore } from '@/stores/master-store'
import { runAps as fetchApsRun, adjustAps as fetchApsAdjust } from '@/api/aps'
import { fetchMaterialShortages } from '@/api/master'
import { toLoadCells, toWorkPlanRows } from '@/data/aps-run-adapter'

interface RunResult {
  workPlans: WorkPlanRow[]
  loadCells: LoadCellOut[]
  kpi: Kpi
}

/** Adjustment pending/applied cho 1 plan (일정조정 dialog) — cần cả 2 đầu window để gọi /aps/adjust. */
interface PlanAdjustment {
  dateStart: string
  dateEnd: string
}

export interface CellSelection { wc: string; date: string; dayIdx: number }

export interface FilterState {
  businessUnit: string
  planType: string
  dateFrom: string   // YYYY-MM-DD
  dateTo: string
  apsDocNo: string
  rev: string
  status: string
  owner: string
  dept: string
}

const EMPTY_KPI: Kpi = {
  onTimeRatePct: 0,
  materialShortageCount: 0,
  overloadWcPct: 0,
  planningRiskCount: 0,
}

export const useApsStore = defineStore('aps', () => {
  const masterStore = useMasterStore()
  const isRunning = ref(false)
  const isSimulating = ref(false)
  // hasData = false trước RUN → panels rỗng nhưng vẫn thấy cột date của range
  const hasData = ref(false)
  const runResult = ref<RunResult | null>(null)

  const filter = ref<FilterState>({
    businessUnit: '전체',
    planType: '',
    dateFrom: '2026-08-01',
    dateTo: '2026-08-31',
    apsDocNo: '',
    rev: '',
    status: '',
    owner: '',
    dept: '',
  })

  const cellSelection = ref<CellSelection | null>(null)
  const selectedRowKey = ref<string | null>(null)
  const confirmedRows = ref<Set<string>>(new Set())
  const dispatchedIds = ref<Set<string>>(new Set())
  // Adjustments pending simulation (key = orderId = WorkPlan.id)
  const pendingAdjustments = ref<Map<string, PlanAdjustment>>(new Map())
  // Adjustments đã được apply sau simulation (persist qua reruns cho tới next RUN APS)
  const appliedAdjustments = ref<Map<string, PlanAdjustment>>(new Map())

  // ── Derived data ────────────────────────────────────────────────────────────

  /** Danh sách ngày hiển thị matrix. Luôn hiện, kể cả trước RUN. */
  const dates = computed<string[]>(() =>
    enumerateDates(filter.value.dateFrom, filter.value.dateTo),
  )

  /** Danh sách WC hiển thị matrix — luôn hiện đầy đủ từ master data (GET /master/work-centers). */
  const workCenters = computed(() => masterStore.workCenters)

  const workPlans = computed<WorkPlanRow[]>(() =>
    hasData.value && runResult.value ? runResult.value.workPlans : [],
  )

  const loadCells = computed<LoadCellOut[]>(() =>
    hasData.value && runResult.value ? runResult.value.loadCells : [],
  )

  const kpi = computed<Kpi>(() =>
    hasData.value && runResult.value ? runResult.value.kpi : EMPTY_KPI,
  )

  /** Index `${wc}::${date}` → cell (chỉ chứa cells trong window). */
  const loadCellIndex = computed<Map<string, LoadCellOut>>(() => {
    const m = new Map<string, LoadCellOut>()
    for (const c of loadCells.value) m.set(`${c.wcCode}::${c.cellDate}`, c)
    return m
  })

  /** Số WO/plan tổng theo WC (dùng cho footer 지시건수). */
  const countByWc = computed<Map<string, number>>(() => {
    const m = new Map<string, number>()
    for (const p of workPlans.value) {
      m.set(p.workcenterNo, (m.get(p.workcenterNo) ?? 0) + 1)
    }
    return m
  })

  /** Σ planned_qty theo WC (dùng cho footer 지시량계). */
  const qtyByWc = computed<Map<string, number>>(() => {
    const m = new Map<string, number>()
    for (const p of workPlans.value) {
      m.set(p.workcenterNo, (m.get(p.workcenterNo) ?? 0) + p.plannedQty)
    }
    return m
  })

  const totalCount = computed<number>(() => workPlans.value.length)
  const totalSum = computed<string>(() => {
    const total = workPlans.value.reduce((s, p) => s + p.plannedQty, 0)
    return total.toLocaleString('en-US')
  })

  /**
   * Work-plan-list filter theo cell được click:
   * - Match wc + planStart <= date <= planEnd (plan có chạm ngày đó).
   */
  const filteredWp = computed<WorkPlanRow[]>(() => {
    const c = cellSelection.value
    if (!c) return workPlans.value
    return workPlans.value.filter(
      (p) => p.workcenterNo === c.wc && p.planStart <= c.date && c.date <= p.planEnd,
    )
  })

  function rowKey(r: WorkPlanRow, idx: number): string {
    return `${r.id}::${idx}`
  }

  /**
   * 3-state badge cho row:
   * - 'pending'    → 대기중: user đã 확인, chưa 시뮬레이션 (adjustment ở pendingAdjustments)
   * - 'solved'     → 해결됨: đã simulate xong và risk hết
   * - 'unresolved' → 미해결: đã simulate xong nhưng risk vẫn còn
   * - null         → chưa 확인 gì
   */
  type BadgeState = 'pending' | 'solved' | 'unresolved' | null
  function badgeStateOf(row: WorkPlanRow, key: string): BadgeState {
    if (pendingAdjustments.value.has(row.id)) return 'pending'
    if (!confirmedRows.value.has(key)) return null
    return row.riskTypes.length === 0 ? 'solved' : 'unresolved'
  }

  // ── Actions ─────────────────────────────────────────────────────────────────

  async function runAps(): Promise<void> {
    isRunning.value = true
    // Reset interactive state — RUN là fresh, adjustments cũ bay hết
    cellSelection.value = null
    selectedRowKey.value = null
    confirmedRows.value = new Set()
    dispatchedIds.value = new Set()
    pendingAdjustments.value = new Map()
    appliedAdjustments.value = new Map()
    try {
      const result = await fetchApsRun()
      // material-shortage được /aps/run rebuild trước khi assemble → fetch sau, không parallel.
      const shortages = await fetchMaterialShortages()
      runResult.value = {
        workPlans: toWorkPlanRows(result.workPlans, shortages),
        loadCells: toLoadCells(result.loadCells),
        kpi: result.kpi,
      }
      hasData.value = true
    } finally {
      isRunning.value = false
    }
  }

  function setCellSelection(sel: CellSelection | null): void {
    const c = cellSelection.value
    if (c && sel && c.wc === sel.wc && c.date === sel.date) {
      cellSelection.value = null
    } else {
      cellSelection.value = sel
    }
  }

  function selectRow(key: string | null): void {
    selectedRowKey.value = key
  }

  interface ConfirmPayload {
    rowKey: string
    orderId: string
    mode: string
    data: { dateStart?: string; dateEnd?: string; memo?: string; reqQty?: number }
  }

  function stageConfirm(payload: ConfirmPayload): void {
    // Chỉ mode adjust / both mới đổi lịch backward (window [dateStart, dateEnd] mới).
    // Mode shortage tạo purchase request, không đổi lịch → không thêm override.
    if ((payload.mode === 'adjust' || payload.mode === 'both') && payload.data.dateStart && payload.data.dateEnd) {
      pendingAdjustments.value = new Map([
        ...pendingAdjustments.value,
        [payload.orderId, { dateStart: payload.data.dateStart, dateEnd: payload.data.dateEnd }],
      ])
    }
    confirmedRows.value = new Set([...confirmedRows.value, payload.rowKey])
  }

  function dispatchWorkOrder(key: string): void {
    dispatchedIds.value = new Set([...dispatchedIds.value, key])
  }

  /**
   * Undo 1 adjustment ĐANG PENDING (chưa simulate). Bỏ khỏi pending + confirmed
   * mark. Adjustment đã simulate (nằm ở appliedAdjustments) không undo được ở đây
   * — user phải RUN APS lại để reset.
   */
  function cancelAdjustment(orderId: string, rowKey: string): void {
    if (pendingAdjustments.value.has(orderId)) {
      const next = new Map(pendingAdjustments.value)
      next.delete(orderId)
      pendingAdjustments.value = next
    }
    if (confirmedRows.value.has(rowKey)) {
      const next = new Set(confirmedRows.value)
      next.delete(rowKey)
      confirmedRows.value = next
    }
  }

  /**
   * Re-backward-fill (POST /aps/adjust) toàn bộ pending adjustments + adjustments đã
   * apply trước đó. Sau sim: pending → applied, matrix + plans + KPI refresh.
   */
  async function runSimulation(): Promise<void> {
    if (!hasData.value) return
    isSimulating.value = true
    try {
      // Merge applied cũ + pending mới. Pending thắng nếu đụng key.
      const merged = new Map<string, PlanAdjustment>(appliedAdjustments.value)
      for (const [k, v] of pendingAdjustments.value) merged.set(k, v)
      const adjustments = Array.from(merged, ([planId, a]) => ({
        planId,
        newStart: a.dateStart,
        newEnd: a.dateEnd,
      }))
      const result = await fetchApsAdjust(null, adjustments)
      // material-shortage được /aps/adjust rebuild trước khi assemble → fetch sau.
      const shortages = await fetchMaterialShortages()
      runResult.value = {
        workPlans: toWorkPlanRows(result.workPlans, shortages),
        loadCells: toLoadCells(result.loadCells),
        kpi: result.kpi,
      }
      appliedAdjustments.value = merged
      pendingAdjustments.value = new Map()
      // Adjustments đã simulate xong → user có thể muốn re-confirm cho phần khác.
      // Giữ confirmedRows để 작업지시 생성 vẫn enable cho row đã confirm.
    } finally {
      isSimulating.value = false
    }
  }

  const pendingCount = computed(() => pendingAdjustments.value.size)

  return {
    isRunning,
    isSimulating,
    hasData,
    filter,
    cellSelection,
    selectedRowKey,
    confirmedRows,
    dispatchedIds,
    workCenters,
    dates,
    workPlans,
    loadCells,
    loadCellIndex,
    kpi,
    countByWc,
    qtyByWc,
    totalCount,
    totalSum,
    filteredWp,
    pendingCount,
    rowKey,
    badgeStateOf,
    runAps,
    setCellSelection,
    selectRow,
    stageConfirm,
    cancelAdjustment,
    dispatchWorkOrder,
    runSimulation,
  }
})
