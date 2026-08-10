// Pinia store — pure mock, gọi `runMockAps()` mỗi lần user bấm RUN APS.
// Contract khớp `aps-backend/app/schemas/aps.py::ApsRunResult`.
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  runMockAps, enumerateDates,
  type ApsRunResult, type LoadCellOut, type WorkPlanRow, type Kpi,
  type AdjustmentOverride,
} from '@/data/mock-scheduler'
import { WORK_CENTERS } from '@/data/master-data'

<<<<<<< HEAD
export interface ApsFilter {
  wcCodes: string[]
  itemCodes: string[]
  risks: RiskType[]
  dateFrom: string | null
  dateTo: string | null
  cellSelection: { wcCode: string; date: string } | null
=======
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
>>>>>>> 0a34f17 (feat(fe): rebuild APS view from XD design with interactive flow)
}

const EMPTY_KPI: Kpi = {
  onTimeRatePct: 0,
  materialShortageCount: 0,
  overloadWcPct: 0,
  planningRiskCount: 0,
}

export interface PendingPurchaseLine {
  itemNo: string
  itemName: string | null
  qty: number
}

export interface PendingPurchaseRequest {
  planId: string
  note: string
  lines: PendingPurchaseLine[]
}

export const useApsStore = defineStore('aps', () => {
  const isRunning = ref(false)
<<<<<<< HEAD
  const filter = ref<ApsFilter>({
    wcCodes: [],
    itemCodes: [],
    risks: [],
    dateFrom: null,
    dateTo: null,
    cellSelection: null,
  })

  const pendingAdjustments = ref<Map<string, PendingAdjustment>>(new Map())
  // Staged, not yet pushed to G-System — POST /erp/purchase-requests only
  // fires when the "Apply" button runs applyAdjustments(), same as staged
  // schedule adjustments (not tied to work-order dispatch).
  const pendingPurchaseRequests = ref<Map<string, PendingPurchaseRequest>>(new Map())

  async function runAps(): Promise<void> {
    isRunning.value = true
    try {
      const result = await apsApi.runAps()
      runId.value = result.run.id
      workPlans.value = result.workPlans
      loadCells.value = result.loadCells
      kpi.value = result.kpi
      selectedPlanId.value = null
      filter.value.cellSelection = null
      // RUN is always G-System-driven — any staged-but-not-yet-Apply'd
      // adjustments/purchase requests are stale against the fresh result.
      pendingAdjustments.value.clear()
      pendingPurchaseRequests.value.clear()
    } finally {
      isRunning.value = false
=======
  // hasData = false trước RUN → panels rỗng nhưng vẫn thấy cột date của range
  const hasData = ref(false)
  const runResult = ref<ApsRunResult | null>(null)

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
  // Adjustments pending simulation (key = orderId)
  const pendingAdjustments = ref<Map<string, AdjustmentOverride>>(new Map())
  // Adjustments đã được apply sau simulation (persist qua reruns cho tới next RUN APS)
  const appliedAdjustments = ref<Map<string, AdjustmentOverride>>(new Map())

  // ── Derived data ────────────────────────────────────────────────────────────

  /** Danh sách ngày hiển thị matrix. Luôn hiện, kể cả trước RUN. */
  const dates = computed<string[]>(() =>
    enumerateDates(filter.value.dateFrom, filter.value.dateTo),
  )

  /** Danh sách WC hiển thị matrix — luôn hiện đầy đủ từ master data. */
  const workCenters = computed(() => WORK_CENTERS)

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
    // Delay giả cho có cảm giác call BE
    await new Promise<void>((res) => setTimeout(res, 400))
    runResult.value = runMockAps(filter.value.dateFrom, filter.value.dateTo)
    hasData.value = true
    isRunning.value = false
  }

  function setCellSelection(sel: CellSelection | null): void {
    const c = cellSelection.value
    if (c && sel && c.wc === sel.wc && c.date === sel.date) {
      cellSelection.value = null
    } else {
      cellSelection.value = sel
>>>>>>> 0a34f17 (feat(fe): rebuild APS view from XD design with interactive flow)
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

<<<<<<< HEAD
  function stagePurchaseRequest(planId: string, note: string, lines: PendingPurchaseLine[]): void {
    pendingPurchaseRequests.value.set(planId, { planId, note, lines })
    pendingPurchaseRequests.value = new Map(pendingPurchaseRequests.value)
  }

  function discardPurchaseRequest(planId: string): void {
    pendingPurchaseRequests.value.delete(planId)
    pendingPurchaseRequests.value = new Map(pendingPurchaseRequests.value)
  }

  // Apply only pushes staged schedule adjustments (/aps/adjust) — staged
  // purchase requests are NOT sent here anymore. They only fire when the
  // matching plan is actually dispatched (see dispatchWorkOrder below).
  async function applyAdjustments(): Promise<void> {
    if (pendingAdjustments.value.size === 0) return

    const drafts = Array.from(pendingAdjustments.value.values())
    const result = await apsApi.adjustAps(runId.value, drafts)
    runId.value = result.run.id
    workPlans.value = result.workPlans
    loadCells.value = result.loadCells
    kpi.value = result.kpi
    pendingAdjustments.value.clear()
  }

  // Actually pushes to G-System (POST /erp/purchase-requests).
  async function requestPurchase(planId: string, note: string, lines: PendingPurchaseLine[]): Promise<void> {
    await erpApi.createPurchaseRequest(planId, note, lines)
  }

  // If this plan has a staged purchase request, send it first — dispatching
  // the work order is what actually flushes a staged purchase request now,
  // not Apply (a plan without a shortage that's never dispatched should
  // never end up pushing a stale purchase request on its own).
  async function dispatchWorkOrder(planId: string): Promise<void> {
    const pending = pendingPurchaseRequests.value.get(planId)
    if (pending) {
      await requestPurchase(pending.planId, pending.note, pending.lines)
      pendingPurchaseRequests.value.delete(planId)
      pendingPurchaseRequests.value = new Map(pendingPurchaseRequests.value)
    }
    await erpApi.createWorkOrder(planId)
  }

  // FE-only preview: a plan with a staged (not-yet-sent) purchase request shows
  // as if the shortage were already resolved — riskType/shortageQty overridden
  // for display only, nothing pushed to G-System until dispatch actually sends
  // it (see dispatchWorkOrder). Never touches the WC×day load matrix (loadCells
  // stay backend-real) — recomputing that grid's material-shortage aggregate
  // client-side would duplicate shortage_builder.py's backward-fill algorithm.
  // Resets automatically: RUN clears pendingPurchaseRequests and refetches the
  // real workPlans, so nothing here can outlive a RUN.
  const displayPlans = computed(() =>
    workPlans.value.map((p) => {
      if (!pendingPurchaseRequests.value.has(p.id)) return p
      if (p.riskType === 'MATERIAL_SHORT') return { ...p, riskType: 'NORMAL' as RiskType, shortageQty: 0 }
      if (p.riskType === 'MATERIAL_AND_OVERLOAD') return { ...p, riskType: 'OVERLOAD' as RiskType, shortageQty: 0 }
      return p
    })
  )

  const selectedPlan = computed(() => displayPlans.value.find((p) => p.id === selectedPlanId.value) ?? null)
  const selectedPending = computed(() =>
    selectedPlanId.value ? pendingAdjustments.value.get(selectedPlanId.value) ?? null : null
  )
  const selectedPendingPurchase = computed(() =>
    selectedPlanId.value ? pendingPurchaseRequests.value.get(selectedPlanId.value) ?? null : null
  )

  const filteredPlans = computed(() => {
    const f = filter.value
    return displayPlans.value.filter((p) => {
      if (f.wcCodes.length && !f.wcCodes.includes(p.wcCode)) return false
      if (f.itemCodes.length && !f.itemCodes.includes(p.itemCode)) return false
      if (f.risks.length && !f.risks.includes(p.riskType)) return false
      // mpsCompletionDate (prod_end_date priority 1, else plan_end_date) must
      // fall inside [dateFrom, dateTo] — same semantics as the backend's
      // _row_matches_filters (work_plan_list.py). Rows with no MPS completion
      // date are dropped once either bound is set.
      if ((f.dateFrom || f.dateTo) && !p.mpsCompletionDate) return false
      if (f.dateFrom && p.mpsCompletionDate! < f.dateFrom) return false
      if (f.dateTo && p.mpsCompletionDate! > f.dateTo) return false
      if (f.cellSelection) {
        if (p.wcCode !== f.cellSelection.wcCode) return false
        if (!p.dailyPlans.some((d) => d.date === f.cellSelection!.date)) return false
      }
      return true
    })
  })

  const selectedCellStatus = computed(() => {
    const sel = filter.value.cellSelection
    if (!sel) return null
    return (
      loadCells.value.find((c) => c.wcCode === sel.wcCode && c.cellDate === sel.date)?.status ??
      null
    )
  })
  const riskCount = computed(() => {
    const cellStatus = selectedCellStatus.value
    if (cellStatus) {
      const cellRisky =
        cellStatus === 'OVERLOAD' ||
        cellStatus === 'MATERIAL_SHORT' ||
        cellStatus === 'OVERLOAD_AND_MATERIAL_SHORT'
      return cellRisky ? filteredPlans.value.length : 0
=======
  function stageConfirm(payload: ConfirmPayload): void {
    // Chỉ mode adjust / both mới đổi lịch backward (dateEnd = new deliveryDate).
    // Mode shortage tạo purchase request, không đổi lịch → không thêm override.
    if ((payload.mode === 'adjust' || payload.mode === 'both') && payload.data.dateEnd) {
      pendingAdjustments.value = new Map([
        ...pendingAdjustments.value,
        [payload.orderId, { deliveryDate: payload.data.dateEnd }],
      ])
>>>>>>> 0a34f17 (feat(fe): rebuild APS view from XD design with interactive flow)
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
   * Re-run backward algorithm với toàn bộ pending adjustments + adjustments đã apply
   * trước đó. Sau sim: pending → applied, matrix + plans + KPI refresh.
   */
  function runSimulation(): void {
    if (!hasData.value) return
    // Merge applied cũ + pending mới. Pending thắng nếu đụng key.
    const merged = new Map<string, AdjustmentOverride>(appliedAdjustments.value)
    for (const [k, v] of pendingAdjustments.value) merged.set(k, v)
    runResult.value = runMockAps(filter.value.dateFrom, filter.value.dateTo, merged)
    appliedAdjustments.value = merged
    pendingAdjustments.value = new Map()
    // Adjustments đã simulate xong → user có thể muốn re-confirm cho phần khác.
    // Giữ confirmedRows để 작업지시 생성 vẫn enable cho row đã confirm.
  }

  const pendingCount = computed(() => pendingAdjustments.value.size)
  const pendingPurchaseCount = computed(() => pendingPurchaseRequests.value.size)

  return {
    isRunning,
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
<<<<<<< HEAD
    selectedPlanId,
    isRunning,
    filter,
    selectedPlan,
    selectedPending,
    selectedPendingPurchase,
    filteredPlans,
    riskCount,
    delayCount,
    pendingCount,
    pendingPurchaseCount,
    pendingAdjustments,
    pendingPurchaseRequests,
    stagePurchaseRequest,
    discardPurchaseRequest,
=======
    countByWc,
    qtyByWc,
    totalCount,
    totalSum,
    filteredWp,
    pendingCount,
    rowKey,
    badgeStateOf,
>>>>>>> 0a34f17 (feat(fe): rebuild APS view from XD design with interactive flow)
    runAps,
    setCellSelection,
    selectRow,
    stageConfirm,
    cancelAdjustment,
    dispatchWorkOrder,
    runSimulation,
  }
})
