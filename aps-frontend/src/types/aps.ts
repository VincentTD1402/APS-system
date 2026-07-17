import type { WorkPlan, LoadCell, ApsRun } from './planning'

export interface KpiSnapshot {
  onTimeRatePct: number
  materialShortageCount: number
  overloadWcPct: number
  planningRiskCount: number
}

export interface ApsRunResult {
  run: ApsRun
  workPlans: WorkPlan[]
  loadCells: LoadCell[]
  kpi: KpiSnapshot
}
