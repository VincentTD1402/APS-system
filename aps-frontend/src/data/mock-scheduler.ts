// Mock scheduler — reproduces BE backward algorithm shape without hitting BE.
// Contract matches `aps-backend/app/schemas/aps.py::ApsRunResult`.
//
// Flow (mirror của `docs/fe-mock-data-explanation-vi.md` §3):
//   1. build task list (MPS + pending WO)
//   2. backward schedule per task → daily_plans
//   3. aggregate load matrix (Σ minutes per WC/date)
//   4. material shortage check (sort by delivery ASC)
//   5. per-plan risk classification
//   6. per-cell status classification
//   7. KPI aggregation

import {
  MOCK_TODAY, MPS_ORDERS, WORK_CENTERS,
  bomOf, findItem, findWc, inventoryTotal, totalRuntimeMinOf,
  type MpsOrder,
} from './master-data'

// ── BE-aligned types ──────────────────────────────────────────────────────────

export type RiskKind = 'overload' | 'material_short'

export interface WorkPlanDailyRow {
  date: string       // YYYY-MM-DD
  qty: number        // EA đổ vào ngày này
  minutes: number    // qty × standardStMin
}

/** Chi tiết thiếu NVL cho 1 plan (khớp BE MaterialShortageRow). */
export interface PlanShortage {
  materialCode: string    // 자재 code (VD: 자재-B)
  requiredQty: number     // qty × qtyPer
  availableQty: number    // stock còn khi đến lượt plan này
  shortageQty: number     // required - available (>0)
}

export interface WorkPlanRow {
  id: string
  sourceType: 'MPS' | 'WO'
  workOrderNo: string | null   // 작업지시번호
  tmpPlanNo: string | null     // (임시)작업계획번호
  orderNo: string | null       // PO
  itemNo: string
  itemName: string
  workcenterNo: string
  workcenterName: string
  procName: string
  plannedQty: number
  planStart: string            // earliest daily_plans.date
  planEnd: string              // latest daily_plans.date (= deliveryDate anchor)
  deliveryDate: string
  riskTypes: RiskKind[]        // empty = normal
  shortageQty: number          // Σ shortageQty của các shortages
  shortages: PlanShortage[]    // breakdown per material (chỉ material thiếu)
  dailyPlans: WorkPlanDailyRow[]
}

export type LoadCellStatus =
  | 'empty'
  | 'normal'
  | 'overload'
  | 'material-shortage'
  | 'urgent'         // overload + shortage cùng ô

export interface LoadCellOut {
  wcCode: string
  cellDate: string
  minutesLoaded: number
  minutesCapacity: number
  status: LoadCellStatus
  plannedQty: number
}

export interface Kpi {
  onTimeRatePct: number         // % plan có planEnd ≤ deliveryDate
  materialShortageCount: number // # plan có material_short
  overloadWcPct: number         // % WC có ≥1 cell overload
  planningRiskCount: number     // # plan có ≥1 risk
}

export interface ApsRunResult {
  runId: string
  startedAt: string
  finishedAt: string
  workPlans: WorkPlanRow[]
  loadCells: LoadCellOut[]
  kpi: Kpi
}

// ── Date helpers ──────────────────────────────────────────────────────────────

function parseYmd(s: string): Date {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d))
}

function fmtYmd(d: Date): string {
  const y = d.getUTCFullYear()
  const m = String(d.getUTCMonth() + 1).padStart(2, '0')
  const dd = String(d.getUTCDate()).padStart(2, '0')
  return `${y}-${m}-${dd}`
}

function addDays(s: string, delta: number): string {
  const d = parseYmd(s)
  d.setUTCDate(d.getUTCDate() + delta)
  return fmtYmd(d)
}

/** Inclusive date range [from, to] as YYYY-MM-DD list. */
export function enumerateDates(from: string, to: string): string[] {
  if (from > to) return []
  const out: string[] = []
  for (let d = from; d <= to; d = addDays(d, 1)) out.push(d)
  return out
}

// ── Step 2. Backward schedule ─────────────────────────────────────────────────

interface AllocationDay { date: string; qty: number }

/**
 * Walk from `endDate` backward, allocating `min(remaining, dailyCap)` each day
 * until qty exhausted or reaches `today`. Overflow at today is dumped into
 * today (rule spec P3 — never schedule before today).
 */
function backwardSchedule(
  qty: number,
  endDate: string,
  today: string,
  dailyCapEa: number,
): AllocationDay[] {
  const out: AllocationDay[] = []
  if (dailyCapEa <= 0 || qty <= 0) return out

  let remaining = qty
  let cursor = endDate
  // Nếu endDate < today (đơn quá hạn) → dồn 100% vào today
  if (cursor < today) cursor = today

  while (remaining > 0 && cursor >= today) {
    const take = Math.min(remaining, dailyCapEa)
    out.unshift({ date: cursor, qty: take })
    remaining -= take
    if (cursor === today) break
    cursor = addDays(cursor, -1)
  }
  // Còn remaining sau khi chạm today → dồn hết vào today
  if (remaining > 0) {
    if (out.length && out[0].date === today) out[0].qty += remaining
    else out.unshift({ date: today, qty: remaining })
  }
  return out
}

// ── Orchestrator ──────────────────────────────────────────────────────────────

interface ScheduleTask extends MpsOrder {
  wcCode: string
  standardStMin: number
  dailyCapEa: number
  totalRuntimeMin: number
}

/** Adjustment override applied bởi user (일정조정 dialog). */
export interface AdjustmentOverride {
  deliveryDate?: string   // ghi đè 납기일자 mới (ISO YYYY-MM-DD)
}

function buildTasks(overrides?: Map<string, AdjustmentOverride>): ScheduleTask[] {
  const tasks: ScheduleTask[] = []
  for (const raw of MPS_ORDERS) {
    const item = findItem(raw.itemCode)
    if (!item?.wcCode || !item.standardStMin) continue
    const wc = findWc(item.wcCode)
    if (!wc) continue
    const totalRuntime = totalRuntimeMinOf(wc)
    // Apply override nếu có (đổi deliveryDate)
    const adj = overrides?.get(raw.id)
    const o: MpsOrder = adj?.deliveryDate ? { ...raw, deliveryDate: adj.deliveryDate } : raw
    tasks.push({
      ...o,
      wcCode: wc.code,
      standardStMin: item.standardStMin,
      totalRuntimeMin: totalRuntime,
      // capacity theo EA/ngày — floor để tránh over-schedule (bám sát BE)
      dailyCapEa: Math.floor(totalRuntime / item.standardStMin),
    })
  }
  return tasks
}

interface Draft {
  task: ScheduleTask
  allocation: AllocationDay[]
  shortages: PlanShortage[]
}

function runShortageCheck(tasks: ScheduleTask[]): Map<string, PlanShortage[]> {
  // Order theo delivery ASC → task gấp được ưu tiên rút tồn kho
  const sorted = [...tasks].sort((a, b) => a.deliveryDate.localeCompare(b.deliveryDate))
  const inv = new Map<string, number>()
  const shortageByTask = new Map<string, PlanShortage[]>()

  // Snapshot inventory
  const rawCodes = new Set<string>()
  for (const t of tasks) for (const b of bomOf(t.itemCode)) rawCodes.add(b.child)
  for (const c of rawCodes) inv.set(c, inventoryTotal(c))

  for (const t of sorted) {
    const perMat: PlanShortage[] = []
    for (const line of bomOf(t.itemCode)) {
      const need = t.qty * line.qtyPer
      const stock = inv.get(line.child) ?? 0
      if (stock < need) {
        perMat.push({
          materialCode: line.child,
          requiredQty: need,
          availableQty: stock,
          shortageQty: need - stock,
        })
        inv.set(line.child, 0)
      } else {
        inv.set(line.child, stock - need)
      }
    }
    if (perMat.length) shortageByTask.set(t.id, perMat)
  }
  return shortageByTask
}

function buildWorkPlan(d: Draft): WorkPlanRow {
  const t = d.task
  const item = findItem(t.itemCode)!
  const wc = findWc(t.wcCode)!
  const dailies: WorkPlanDailyRow[] = d.allocation.map((a) => ({
    date: a.date,
    qty: a.qty,
    minutes: +(a.qty * t.standardStMin).toFixed(2),
  }))
  const planStart = dailies.length ? dailies[0].date : t.deliveryDate
  const planEnd   = dailies.length ? dailies[dailies.length - 1].date : t.deliveryDate
  const shortageQty = d.shortages.reduce((s, x) => s + x.shortageQty, 0)
  return {
    id: t.id,
    sourceType: t.sourceType,
    workOrderNo: t.sourceType === 'WO' ? t.workOrderNo : null,
    tmpPlanNo:   t.sourceType === 'MPS' ? t.id : null,
    orderNo: t.id,
    itemNo: item.code,
    itemName: item.nameKo,
    workcenterNo: wc.code,
    workcenterName: wc.nameKo,
    procName: `${wc.nameKo} 공정`,
    plannedQty: t.qty,
    planStart,
    planEnd,
    deliveryDate: t.deliveryDate,
    riskTypes: [],           // filled below
    shortageQty,
    shortages: d.shortages,
    dailyPlans: dailies,
  }
}

/**
 * Aggregate minutes theo (wc, date). Chỉ dùng để detect overload.
 * Key = `${wc}::${date}`.
 */
function aggregateLoad(plans: WorkPlanRow[]): {
  loadByCell: Map<string, number>
  qtyByCell: Map<string, number>
} {
  const loadByCell = new Map<string, number>()
  const qtyByCell = new Map<string, number>()
  for (const p of plans) {
    for (const dp of p.dailyPlans) {
      const k = `${p.workcenterNo}::${dp.date}`
      loadByCell.set(k, (loadByCell.get(k) ?? 0) + dp.minutes)
      qtyByCell.set(k, (qtyByCell.get(k) ?? 0) + dp.qty)
    }
  }
  return { loadByCell, qtyByCell }
}

/**
 * Public entry — chạy full mock APS cho window `[dateFrom, dateTo]`.
 * Backward algorithm luôn dùng MOCK_TODAY làm floor; range chỉ crop cells hiển thị.
 */
export function runMockAps(
  dateFrom: string,
  dateTo: string,
  overrides?: Map<string, AdjustmentOverride>,
): ApsRunResult {
  const startedAt = new Date().toISOString()

  // 1. tasks (áp overrides từ 일정조정)
  const tasks = buildTasks(overrides)

  // 2. backward per task
  const drafts: Draft[] = tasks.map((t) => ({
    task: t,
    allocation: backwardSchedule(t.qty, t.deliveryDate, MOCK_TODAY, t.dailyCapEa),
    shortages: [],
  }))

  // 4. shortage check (chạy song song với alloc, không phụ thuộc)
  const shortageMap = runShortageCheck(tasks)
  for (const d of drafts) {
    d.shortages = shortageMap.get(d.task.id) ?? []
  }

  const workPlans = drafts.map(buildWorkPlan)

  // 3. aggregate load
  const { loadByCell, qtyByCell } = aggregateLoad(workPlans)

  // Cache capacity của mỗi WC
  const capByWc = new Map<string, number>()
  for (const w of WORK_CENTERS) capByWc.set(w.code, totalRuntimeMinOf(w))

  // 5a. Xây shortageCells trước từ các plan có BOM shortage thực sự
  const shortageCells = new Set<string>()
  for (const p of workPlans) {
    if (p.shortageQty <= 0) continue
    for (const dp of p.dailyPlans) shortageCells.add(`${p.workcenterNo}::${dp.date}`)
  }

  // 5b. Per-plan risk — cả overload và material_short đều day-based:
  // - overload: plan chạm ngày mà load tổng > capacity
  // - material_short: plan chạm ngày mà có shortage (từ plan này HOẶC plan khác cùng WC)
  // Điều này khớp với màu ô ở matrix: chip = worst status của các ô plan touches.
  for (const p of workPlans) {
    const cap = capByWc.get(p.workcenterNo) ?? 0
    const overload = p.dailyPlans.some(
      (dp) => (loadByCell.get(`${p.workcenterNo}::${dp.date}`) ?? 0) > cap,
    )
    const touchesShortage = p.dailyPlans.some(
      (dp) => shortageCells.has(`${p.workcenterNo}::${dp.date}`),
    )
    if (touchesShortage) p.riskTypes.push('material_short')
    if (overload) p.riskTypes.push('overload')
  }

  // 6. per-cell status — enumerate [dateFrom, dateTo] × WC
  const dates = enumerateDates(dateFrom, dateTo)
  const loadCells: LoadCellOut[] = []
  for (const w of WORK_CENTERS) {
    const cap = capByWc.get(w.code) ?? 0
    for (const d of dates) {
      const k = `${w.code}::${d}`
      const loaded = loadByCell.get(k) ?? 0
      const qty = qtyByCell.get(k) ?? 0
      const isOverload = loaded > cap
      const isShortage = shortageCells.has(k)
      let status: LoadCellStatus = 'empty'
      if (loaded === 0 && !isShortage) status = 'empty'
      else if (isOverload && isShortage) status = 'urgent'
      else if (isOverload) status = 'overload'
      else if (isShortage) status = 'material-shortage'
      else status = 'normal'
      loadCells.push({
        wcCode: w.code,
        cellDate: d,
        minutesLoaded: +loaded.toFixed(2),
        minutesCapacity: +cap.toFixed(2),
        status,
        plannedQty: qty,
      })
    }
  }

  // 7. KPI
  const total = workPlans.length
  const onTime = workPlans.filter((p) => p.planEnd <= p.deliveryDate).length
  const shortCnt = workPlans.filter((p) => p.riskTypes.includes('material_short')).length
  const wcsWithOverload = new Set<string>()
  for (const c of loadCells) if (c.status === 'overload' || c.status === 'urgent') wcsWithOverload.add(c.wcCode)
  const riskCnt = workPlans.filter((p) => p.riskTypes.length > 0).length
  const kpi: Kpi = {
    onTimeRatePct: total ? +((onTime / total) * 100).toFixed(1) : 0,
    materialShortageCount: shortCnt,
    overloadWcPct: WORK_CENTERS.length
      ? +((wcsWithOverload.size / WORK_CENTERS.length) * 100).toFixed(1)
      : 0,
    planningRiskCount: riskCnt,
  }

  return {
    runId: `run-${startedAt}`,
    startedAt,
    finishedAt: new Date().toISOString(),
    workPlans,
    loadCells,
    kpi,
  }
}
