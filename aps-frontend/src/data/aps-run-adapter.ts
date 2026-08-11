// Maps `POST /aps/run` + `POST /aps/adjust` responses (types/aps.ts, types/planning.ts)
// into the display shapes the APS work-plan components expect (mock-scheduler.ts).
import type { WorkPlan, LoadCell } from '@/types/planning'
import type { MaterialShortageRow } from '@/types/master'
import type { LoadCellOut, LoadCellStatus, PlanShortage, RiskKind, WorkPlanRow } from './mock-scheduler'

const RISK_TYPE_MAP: Record<string, RiskKind[]> = {
  NORMAL: [],
  MATERIAL_SHORT: ['material_short'],
  OVERLOAD: ['overload'],
  MATERIAL_AND_OVERLOAD: ['overload', 'material_short'],
}

const LOAD_STATUS_MAP: Record<string, LoadCellStatus> = {
  NORMAL: 'normal',
  OVERLOAD: 'overload',
  MATERIAL_SHORT: 'material-shortage',
  OVERLOAD_AND_MATERIAL_SHORT: 'urgent',
}

const SOURCE_TYPE_MAP: Record<string, 'MPS' | 'WO'> = {
  FROM_MPS: 'MPS',
  FROM_WORK_ORDER: 'WO',
}

/** Per-plan breakdown — components thiếu của item mà plan này sản xuất. */
function shortagesForItem(itemCode: string, shortages: MaterialShortageRow[]): PlanShortage[] {
  return shortages
    .filter((s) => s.parentItemNo === itemCode && s.isShort)
    .map((s) => ({
      materialCode: s.itemNo ?? s.itemName ?? '-',
      requiredQty: s.requiredQty,
      availableQty: s.availableQty,
      shortageQty: s.shortageQty,
    }))
}

export function toWorkPlanRows(workPlans: WorkPlan[], shortages: MaterialShortageRow[]): WorkPlanRow[] {
  return workPlans.map((wp) => ({
    id: wp.id,
    sourceType: SOURCE_TYPE_MAP[wp.sourceType] ?? 'MPS',
    workOrderNo: wp.workOrderNo,
    tmpPlanNo: wp.tmpPlanNo,
    orderNo: wp.orderNo,
    itemNo: wp.itemCode,
    itemName: wp.itemNameKo,
    workcenterNo: wp.wcCode,
    workcenterName: wp.wcName ?? '',
    procName: wp.processNameKo,
    plannedQty: wp.planQty,
    planStart: wp.planStartDate,
    planEnd: wp.planEndDate,
    deliveryDate: wp.deliveryDate,
    riskTypes: RISK_TYPE_MAP[wp.riskType] ?? [],
    shortageQty: wp.shortageQty,
    shortages: shortagesForItem(wp.itemCode, shortages),
    dailyPlans: wp.dailyPlans.map((d) => ({ date: d.date, qty: d.qty, minutes: d.minutes })),
  }))
}

export function toLoadCells(loadCells: LoadCell[]): LoadCellOut[] {
  return loadCells.map((c) => ({
    wcCode: c.wcCode,
    cellDate: c.cellDate,
    minutesLoaded: c.minutesLoaded,
    minutesCapacity: c.minutesCapacity,
    status: LOAD_STATUS_MAP[c.status] ?? 'normal',
    plannedQty: 0,
  }))
}
