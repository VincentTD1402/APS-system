import type { WorkCenter, Item, Routing, BomComponent, InventoryRow } from '@/types/master'
import type { Mps, ErpOutboxRow, WorkPlanDaily } from '@/types/planning'
import type { ApsRunResult } from '@/types/aps'
import type { PendingAdjustment } from '@/stores/aps-store'
import type { LoadCellStatus } from '@/types/enums'
import dayjs from 'dayjs'
import {
  MOCK_WORK_CENTERS,
  MOCK_ITEMS,
  MOCK_ROUTINGS,
  MOCK_BOM,
  MOCK_INVENTORY,
  MOCK_TODAY,
} from '@/mocks/master-data'
import { MOCK_MPS } from '@/mocks/mps-data'
import { runMockAps } from '@/mocks/mock-scheduler'

const state = {
  mps: [...MOCK_MPS] as Mps[],
  lastRun: null as ApsRunResult | null,
  outbox: [] as ErpOutboxRow[],
}

function delay<T>(v: T, ms = 200): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(v), ms))
}

function backwardFill(
  qty: number,
  startDate: string,
  endDate: string,
  dailyCapEa: number,
  standardStMin: number
): WorkPlanDaily[] {
  const plans: WorkPlanDaily[] = []
  let remaining = qty
  let cursor = dayjs(endDate)
  const start = dayjs(startDate)
  while (remaining > 0 && !cursor.isBefore(start)) {
    const qtyDay = Math.min(dailyCapEa, remaining)
    plans.push({
      date: cursor.format('YYYY-MM-DD'),
      qty: qtyDay,
      minutes: Math.round(qtyDay * standardStMin),
    })
    remaining -= qtyDay
    cursor = cursor.subtract(1, 'day')
  }
  if (remaining > 0) {
    // Dư khi lùi tới start_date → dồn vào start_date (cell sẽ over capa → cam)
    const startStr = start.format('YYYY-MM-DD')
    const existing = plans.find((p) => p.date === startStr)
    if (existing) {
      existing.qty += remaining
      existing.minutes = Math.round(existing.qty * standardStMin)
    } else {
      plans.push({
        date: startStr,
        qty: remaining,
        minutes: Math.round(remaining * standardStMin),
      })
    }
  }
  plans.sort((a, b) => a.date.localeCompare(b.date))
  return plans
}

function reclassifyCell(
  minutesLoaded: number,
  capacity: number,
  hasMaterialShort: boolean
): LoadCellStatus {
  if (minutesLoaded === 0) return 'EMPTY'
  const overload = minutesLoaded > capacity
  if (overload && hasMaterialShort) return 'OVERLOAD_AND_MATERIAL_SHORT'
  if (overload) return 'OVERLOAD'
  if (hasMaterialShort) return 'MATERIAL_SHORT'
  return 'NORMAL'
}

export const mockServer = {
  today: MOCK_TODAY,

  listWorkCenters(): Promise<WorkCenter[]> {
    return delay(MOCK_WORK_CENTERS)
  },
  listItems(): Promise<Item[]> {
    return delay(MOCK_ITEMS)
  },
  listRoutings(): Promise<Routing[]> {
    return delay(MOCK_ROUTINGS)
  },
  listBom(): Promise<BomComponent[]> {
    return delay(MOCK_BOM)
  },
  listInventory(): Promise<InventoryRow[]> {
    return delay(MOCK_INVENTORY)
  },

  listMps(): Promise<Mps[]> {
    return delay(state.mps)
  },

  async runAps(): Promise<ApsRunResult> {
    const result = runMockAps()
    state.lastRun = result
    return delay(result, 600)
  },

  async applyPending(drafts: PendingAdjustment[]): Promise<ApsRunResult> {
    if (!state.lastRun) return delay(state.lastRun as unknown as ApsRunResult)
    const run = state.lastRun

    const routingByItem = Object.fromEntries(MOCK_ROUTINGS.map((r) => [r.itemCode, r]))
    const wcCapacity: Record<string, number> = Object.fromEntries(
      MOCK_WORK_CENTERS.map((w) => [w.code, w.totalRuntimeMin])
    )

    const cellIndex = new Map<string, { minutesLoaded: number; hasMaterialShort: boolean }>()
    for (const c of run.loadCells) {
      cellIndex.set(`${c.wcCode}|${c.cellDate}`, {
        minutesLoaded: c.minutesLoaded,
        hasMaterialShort: c.status === 'MATERIAL_SHORT' || c.status === 'OVERLOAD_AND_MATERIAL_SHORT',
      })
    }

    for (const draft of drafts) {
      const plan = run.workPlans.find((p) => p.id === draft.planId)
      if (!plan) continue
      const routing = routingByItem[plan.itemCode]
      if (!routing) continue

      const wcCap = wcCapacity[plan.wcCode] ?? 480
      const dailyCapEa = Math.floor(wcCap / routing.standardStMin)

      // 1. Subtract old contribution from cells (dùng dailyPlans hiện tại — exact minutes)
      for (const dp of plan.dailyPlans) {
        const key = `${plan.wcCode}|${dp.date}`
        const cur = cellIndex.get(key)
        if (cur) cur.minutesLoaded = Math.max(0, cur.minutesLoaded - dp.minutes)
      }

      // 2. Backward fill trên [newStart, newEnd] với EA capa/ngày
      const newDailyPlans = backwardFill(
        plan.planQty,
        draft.newStart,
        draft.newEnd,
        dailyCapEa,
        routing.standardStMin
      )

      // 3. Add new contribution
      for (const dp of newDailyPlans) {
        const key = `${plan.wcCode}|${dp.date}`
        const cur = cellIndex.get(key) ?? { minutesLoaded: 0, hasMaterialShort: false }
        cur.minutesLoaded += dp.minutes
        if (plan.riskType === 'MATERIAL_SHORT' || plan.riskType === 'MATERIAL_AND_OVERLOAD')
          cur.hasMaterialShort = true
        cellIndex.set(key, cur)
      }

      // 4. Commit plan state
      if (!plan.adjusted) {
        plan.originalStart = plan.planStartDate
        plan.originalEnd = plan.planEndDate
      }
      plan.planStartDate = draft.newStart
      plan.planEndDate = draft.newEnd
      plan.adjusted = true
      plan.dailyPlans = newDailyPlans

      // 5. Re-classify risk cho plan chỉnh — check cell overload trên newDates
      const anyOverload = newDailyPlans.some((dp) => {
        const key = `${plan.wcCode}|${dp.date}`
        const c = cellIndex.get(key)
        return c ? c.minutesLoaded > wcCap : false
      })
      const wasMaterial =
        plan.riskType === 'MATERIAL_SHORT' || plan.riskType === 'MATERIAL_AND_OVERLOAD'
      plan.riskType = wasMaterial
        ? anyOverload
          ? 'MATERIAL_AND_OVERLOAD'
          : 'MATERIAL_SHORT'
        : anyOverload
          ? 'OVERLOAD'
          : 'NORMAL'
    }

    run.loadCells = Array.from(cellIndex.entries()).map(([key, val]) => {
      const [wcCode, cellDate] = key.split('|')
      const capacity = wcCapacity[wcCode] ?? 480
      return {
        wcCode,
        cellDate,
        minutesLoaded: Math.round(val.minutesLoaded),
        minutesCapacity: capacity,
        status: reclassifyCell(val.minutesLoaded, capacity, val.hasMaterialShort),
      }
    })

    const total = run.workPlans.length
    const onTime = run.workPlans.filter((p) => p.planEndDate <= p.deliveryDate).length
    const matCount = run.workPlans.filter(
      (p) => p.riskType === 'MATERIAL_SHORT' || p.riskType === 'MATERIAL_AND_OVERLOAD'
    ).length
    const overloadWcs = new Set(
      run.loadCells
        .filter((c) => c.status === 'OVERLOAD' || c.status === 'OVERLOAD_AND_MATERIAL_SHORT')
        .map((c) => c.wcCode)
    )
    const riskCount = run.workPlans.filter((p) => p.riskType !== 'NORMAL').length
    run.kpi = {
      onTimeRatePct: total ? Math.round((onTime / total) * 1000) / 10 : 100,
      materialShortageCount: matCount,
      overloadWcPct: MOCK_WORK_CENTERS.length
        ? Math.round((overloadWcs.size / MOCK_WORK_CENTERS.length) * 1000) / 10
        : 0,
      planningRiskCount: riskCount,
    }

    return delay(run, 300)
  },

  createPurchaseRequest(planId: string, qty: number, note: string): Promise<ErpOutboxRow> {
    const row: ErpOutboxRow = {
      id: `pr-${state.outbox.length + 1}`,
      runId: state.lastRun?.run.id ?? null,
      action: 'CREATE_PURCHASE_REQUEST',
      payload: { planId, qty, note },
      status: 'PENDING',
      createdAt: new Date().toISOString(),
      pushedAt: null,
      error: null,
    }
    state.outbox.push(row)
    setTimeout(() => {
      row.status = 'PUSHED'
      row.pushedAt = new Date().toISOString()
    }, 1200)
    return delay(row)
  },

  createWorkOrder(planId: string): Promise<ErpOutboxRow> {
    const row: ErpOutboxRow = {
      id: `wo-${state.outbox.length + 1}`,
      runId: state.lastRun?.run.id ?? null,
      action: 'CREATE_WORK_ORDER',
      payload: { planId },
      status: 'PENDING',
      createdAt: new Date().toISOString(),
      pushedAt: null,
      error: null,
    }
    state.outbox.push(row)
    setTimeout(() => {
      row.status = 'PUSHED'
      row.pushedAt = new Date().toISOString()
    }, 1200)
    return delay(row)
  },

  listOutbox(): Promise<ErpOutboxRow[]> {
    return delay(state.outbox)
  },
}
