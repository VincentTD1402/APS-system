import dayjs from 'dayjs'
import type { WorkPlan, LoadCell, ApsRun } from '@/types/planning'
import type { KpiSnapshot, ApsRunResult } from '@/types/aps'
import type { LoadCellStatus, RiskType } from '@/types/enums'
import {
  MOCK_WORK_CENTERS,
  MOCK_ROUTINGS,
  MOCK_BOM,
  MOCK_INVENTORY,
  MOCK_ITEMS,
  MOCK_TODAY,
} from './master-data'
import { MOCK_MPS, MOCK_WORK_ORDERS } from './mps-data'

interface DailyPlan {
  date: string
  qty: number
  minutes: number
}

interface ScheduleTask {
  sourceType: 'FROM_WORK_ORDER' | 'FROM_MPS'
  workOrderNo: string | null
  tmpPlanNo: string
  orderNo: string
  itemCode: string
  wcCode: string
  planQty: number
  endDate: string
  deliveryDate: string
  presetStart: string | null
  presetEnd: string | null
}

function backwardSchedule(
  planQty: number,
  endDate: string,
  today: string,
  dailyCapacityEa: number
): DailyPlan[] {
  const plans: DailyPlan[] = []
  let remaining = planQty
  let cursor = dayjs(endDate)
  const todayD = dayjs(today)

  while (remaining > 0 && !cursor.isBefore(todayD)) {
    const qty = Math.min(dailyCapacityEa, remaining)
    plans.push({ date: cursor.format('YYYY-MM-DD'), qty, minutes: 0 })
    remaining -= qty
    cursor = cursor.subtract(1, 'day')
  }
  if (remaining > 0) {
    const todayStr = todayD.format('YYYY-MM-DD')
    const existing = plans.find((p) => p.date === todayStr)
    if (existing) {
      existing.qty += remaining
    } else {
      plans.push({ date: todayStr, qty: remaining, minutes: 0 })
    }
  }
  plans.sort((a, b) => a.date.localeCompare(b.date))
  return plans
}

function wcCapacityMap(): Record<string, number> {
  const m: Record<string, number> = {}
  for (const wc of MOCK_WORK_CENTERS) {
    m[wc.code] = wc.totalRuntimeMin
  }
  return m
}

function checkMaterialShortages(
  tasks: (ScheduleTask & { plans: DailyPlan[] })[]
): Map<string, { risk: RiskType; shortageQty: number }> {
  const result = new Map<string, { risk: RiskType; shortageQty: number }>()
  const inventoryByItem: Record<string, number> = {}
  for (const inv of MOCK_INVENTORY) {
    inventoryByItem[inv.itemCode] = (inventoryByItem[inv.itemCode] ?? 0) + inv.onHand
  }
  const sorted = [...tasks].sort((a, b) => a.deliveryDate.localeCompare(b.deliveryDate))
  for (const task of sorted) {
    const components = MOCK_BOM.filter((b) => b.parentItemCode === task.itemCode)
    let shortage = 0
    for (const comp of components) {
      const need = task.planQty * comp.qtyPer
      const stock = inventoryByItem[comp.childItemCode] ?? 0
      if (need > stock) {
        shortage += need - stock
        inventoryByItem[comp.childItemCode] = 0
      } else {
        inventoryByItem[comp.childItemCode] = stock - need
      }
    }
    result.set(task.tmpPlanNo, {
      risk: shortage > 0 ? 'MATERIAL_SHORT' : 'NORMAL',
      shortageQty: shortage,
    })
  }
  return result
}

export function runMockAps(today: string = MOCK_TODAY): ApsRunResult {
  const routingByItem: Record<string, (typeof MOCK_ROUTINGS)[0]> = {}
  for (const r of MOCK_ROUTINGS) routingByItem[r.itemCode] = r
  const caps = wcCapacityMap()
  const itemByCode = Object.fromEntries(MOCK_ITEMS.map((i) => [i.code, i]))

  const tasks: ScheduleTask[] = []
  let counter = 1
  for (const wo of MOCK_WORK_ORDERS) {
    if (wo.status !== 'PENDING') continue
    tasks.push({
      sourceType: 'FROM_WORK_ORDER',
      workOrderNo: wo.woNo,
      tmpPlanNo: `WP-${String(counter++).padStart(4, '0')}`,
      orderNo: wo.woNo,
      itemCode: wo.itemCode,
      wcCode: wo.wcCode,
      planQty: wo.planQty,
      endDate: wo.planEndDate,
      deliveryDate: wo.planEndDate,
      presetStart: wo.planStartDate,
      presetEnd: wo.planEndDate,
    })
  }
  for (const mps of MOCK_MPS) {
    if (mps.status !== 'DRAFT') continue
    const routing = routingByItem[mps.itemCode]
    if (!routing) continue
    tasks.push({
      sourceType: 'FROM_MPS',
      workOrderNo: null,
      tmpPlanNo: `WP-${String(counter++).padStart(4, '0')}`,
      orderNo: mps.orderNo,
      itemCode: mps.itemCode,
      wcCode: routing.wcCode,
      planQty: mps.planQty,
      endDate: mps.workEndDate ?? mps.endDate,
      deliveryDate: mps.endDate,
      presetStart: mps.workStartDate,
      presetEnd: mps.workEndDate,
    })
  }

  const withPlans: (ScheduleTask & { plans: DailyPlan[] })[] = tasks.map((t) => {
    const routing = routingByItem[t.itemCode]
    if (!routing) return { ...t, plans: [] }
    const capMin = caps[t.wcCode] ?? 480
    const dailyCap = Math.floor(capMin / routing.standardStMin)
    const plans = backwardSchedule(t.planQty, t.endDate, today, dailyCap)
    for (const p of plans) p.minutes = Math.round(p.qty * routing.standardStMin)
    return { ...t, plans }
  })

  const cellMap = new Map<string, { minutesLoaded: number; hasMaterialShort: boolean }>()
  const materialResults = checkMaterialShortages(withPlans)

  for (const task of withPlans) {
    const mat = materialResults.get(task.tmpPlanNo)
    for (const dp of task.plans) {
      const key = `${task.wcCode}|${dp.date}`
      const cur = cellMap.get(key) ?? { minutesLoaded: 0, hasMaterialShort: false }
      cur.minutesLoaded += dp.minutes
      if (mat?.risk === 'MATERIAL_SHORT') cur.hasMaterialShort = true
      cellMap.set(key, cur)
    }
  }

  const loadCells: LoadCell[] = []
  for (const [key, val] of cellMap) {
    const [wcCode, cellDate] = key.split('|')
    const capacity = caps[wcCode] ?? 480
    const overload = val.minutesLoaded > capacity
    let status: LoadCellStatus = 'NORMAL'
    if (val.minutesLoaded === 0) status = 'EMPTY'
    else if (overload && val.hasMaterialShort) status = 'OVERLOAD_AND_MATERIAL_SHORT'
    else if (overload) status = 'OVERLOAD'
    else if (val.hasMaterialShort) status = 'MATERIAL_SHORT'
    loadCells.push({ wcCode, cellDate, minutesLoaded: val.minutesLoaded, minutesCapacity: capacity, status })
  }

  const workPlans: WorkPlan[] = withPlans.map((t) => {
    const mat = materialResults.get(t.tmpPlanNo) ?? { risk: 'NORMAL' as RiskType, shortageQty: 0 }
    const dates = t.plans.map((p) => p.date).sort()
    const start = t.presetStart ?? dates[0] ?? today
    const end = t.presetEnd ?? dates[dates.length - 1] ?? t.endDate
    const overloadCell = t.plans.some((dp) => {
      const key = `${t.wcCode}|${dp.date}`
      const cell = cellMap.get(key)
      const cap = caps[t.wcCode] ?? 480
      return cell ? cell.minutesLoaded > cap : false
    })
    let risk: RiskType = mat.risk
    if (overloadCell && risk === 'MATERIAL_SHORT') risk = 'MATERIAL_AND_OVERLOAD'
    else if (overloadCell) risk = 'OVERLOAD'
    const routing = routingByItem[t.itemCode]
    const item = itemByCode[t.itemCode]
    return {
      id: crypto.randomUUID(),
      runId: 'mock-run',
      sourceType: t.sourceType,
      workOrderNo: t.workOrderNo,
      tmpPlanNo: t.tmpPlanNo,
      orderNo: t.orderNo,
      itemCode: t.itemCode,
      itemNameKo: item?.nameKo ?? t.itemCode,
      itemNameVi: item?.nameVi ?? t.itemCode,
      wcCode: t.wcCode,
      processNameKo: routing?.processNameKo ?? '',
      processNameVi: routing?.processNameVi ?? '',
      planQty: t.planQty,
      planStartDate: start,
      planEndDate: end,
      deliveryDate: t.deliveryDate,
      riskType: risk,
      shortageQty: mat.shortageQty,
      adjusted: false,
      originalStart: null,
      originalEnd: null,
      dailyPlans: t.plans.map((p) => ({ date: p.date, qty: p.qty, minutes: p.minutes })),
    }
  })

  const totalPlans = workPlans.length
  const onTime = workPlans.filter((p) => p.planEndDate <= p.deliveryDate).length
  const matCount = workPlans.filter(
    (p) => p.riskType === 'MATERIAL_SHORT' || p.riskType === 'MATERIAL_AND_OVERLOAD'
  ).length
  const overloadWcs = new Set(
    loadCells.filter((c) => c.status === 'OVERLOAD' || c.status === 'OVERLOAD_AND_MATERIAL_SHORT').map((c) => c.wcCode)
  )
  const riskCount = workPlans.filter((p) => p.riskType !== 'NORMAL').length

  const kpi: KpiSnapshot = {
    onTimeRatePct: totalPlans ? Math.round((onTime / totalPlans) * 1000) / 10 : 100,
    materialShortageCount: matCount,
    overloadWcPct: MOCK_WORK_CENTERS.length
      ? Math.round((overloadWcs.size / MOCK_WORK_CENTERS.length) * 1000) / 10
      : 0,
    planningRiskCount: riskCount,
  }

  const run: ApsRun = {
    id: 'mock-run',
    startedAt: new Date().toISOString(),
    finishedAt: new Date().toISOString(),
  }

  return { run, workPlans, loadCells, kpi }
}
