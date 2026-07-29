import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { WorkPlan, LoadCell } from '@/types/planning'
import type { KpiSnapshot } from '@/types/aps'
import type { RiskType } from '@/types/enums'
import * as apsApi from '@/api/aps'
import * as erpApi from '@/api/erp'

export interface ApsFilter {
  wcCodes: string[]
  itemCodes: string[]
  risks: RiskType[]
  dateFrom: string | null
  dateTo: string | null
  cellSelection: { wcCode: string; date: string } | null
}

export interface PendingAdjustment {
  planId: string
  newStart: string
  newEnd: string
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
  const runId = ref<string | null>(null)
  const workPlans = ref<WorkPlan[]>([])
  const loadCells = ref<LoadCell[]>([])
  const kpi = ref<KpiSnapshot | null>(null)
  const selectedPlanId = ref<string | null>(null)
  const isRunning = ref(false)
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
    }
  }

  function stageAdjustment(planId: string, newStart: string, newEnd: string): void {
    pendingAdjustments.value.set(planId, { planId, newStart, newEnd })
    pendingAdjustments.value = new Map(pendingAdjustments.value)
  }

  function discardPending(planId: string): void {
    pendingAdjustments.value.delete(planId)
    pendingAdjustments.value = new Map(pendingAdjustments.value)
  }

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
    }
    return filteredPlans.value.filter((p) => p.riskType !== 'NORMAL').length
  })
  const delayCount = computed(() => filteredPlans.value.filter((p) => p.planEndDate > p.deliveryDate).length)
  const pendingCount = computed(() => pendingAdjustments.value.size)
  const pendingPurchaseCount = computed(() => pendingPurchaseRequests.value.size)

  return {
    runId,
    workPlans,
    loadCells,
    kpi,
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
    runAps,
    stageAdjustment,
    discardPending,
    applyAdjustments,
    requestPurchase,
    dispatchWorkOrder,
  }
})
