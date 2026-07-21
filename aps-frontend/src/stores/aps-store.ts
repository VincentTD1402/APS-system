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
  cellSelection: { wcCode: string; date: string } | null
}

export interface PendingAdjustment {
  planId: string
  newStart: string
  newEnd: string
}

export const useApsStore = defineStore('aps', () => {
  const runId = ref<string | null>(null)
  const workPlans = ref<WorkPlan[]>([])
  const loadCells = ref<LoadCell[]>([])
  const kpi = ref<KpiSnapshot | null>(null)
  const selectedPlanId = ref<string | null>(null)
  const isRunning = ref(false)
  const filter = ref<ApsFilter>({ wcCodes: [], itemCodes: [], risks: [], cellSelection: null })

  const pendingAdjustments = ref<Map<string, PendingAdjustment>>(new Map())

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
      pendingAdjustments.value.clear()
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

  async function requestPurchase(planId: string, qty: number, note: string): Promise<void> {
    await erpApi.createPurchaseRequest(planId, qty, note)
  }

  async function dispatchWorkOrder(planId: string): Promise<void> {
    await erpApi.createWorkOrder(planId)
  }

  const selectedPlan = computed(() => workPlans.value.find((p) => p.id === selectedPlanId.value) ?? null)
  const selectedPending = computed(() =>
    selectedPlanId.value ? pendingAdjustments.value.get(selectedPlanId.value) ?? null : null
  )

  const filteredPlans = computed(() => {
    const f = filter.value
    return workPlans.value.filter((p) => {
      if (f.wcCodes.length && !f.wcCodes.includes(p.wcCode)) return false
      if (f.itemCodes.length && !f.itemCodes.includes(p.itemCode)) return false
      if (f.risks.length && !f.risks.includes(p.riskType)) return false
      if (f.cellSelection) {
        if (p.wcCode !== f.cellSelection.wcCode) return false
        if (p.planStartDate > f.cellSelection.date || p.planEndDate < f.cellSelection.date) return false
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
    filteredPlans,
    riskCount,
    delayCount,
    pendingCount,
    pendingAdjustments,
    runAps,
    stageAdjustment,
    discardPending,
    applyAdjustments,
    requestPurchase,
    dispatchWorkOrder,
  }
})
