// Mirrors aps-backend/app/schemas/work_plan_recommendation.py.
// BE serialises camelCase (CamelModel), so these names match the wire format 1:1.
//
// Split of responsibility, worth keeping in mind when rendering: every number
// lives in `facts` and is computed by the backend from aps_daily_plan /
// aps_material_shortage. `narrative` is prose only — the LLM never supplies a
// figure. Render numbers from `facts`, never by parsing the prose.

export interface OverloadDay {
  workDate: string // YYYY-MM-DD
  loadPercent: number
  usedMinutes: number
  capacityMinutes: number
}

export interface WorkcenterOverload {
  workcenterNo: string | null
  workcenterName: string | null
  /** Overloaded days, loadPercent descending. */
  overloadDays: OverloadDay[]
  overloadDayCount: number
  peakDay: string | null
  peakLoadPercent: number
}

export interface AffectedPlanRef {
  id: string
  /** 작업지시번호 — confirmed work orders only. */
  workOrderNo: string | null
  /** (임시)작업계획번호 — temporary MPS plans only. */
  tmpPlanNo: string | null
  orderNo: string | null
  itemNo: string | null
  workcenterNo: string | null
  deliveryDate: string | null
  riskTypes: string[]
}

export interface AffectedPlans {
  /** Full count — `sample` is capped, so never derive the total from its length. */
  count: number
  sample: AffectedPlanRef[]
}

export interface ShortageComponent {
  parentItemNo: string | null
  itemNo: string | null
  itemName: string | null
  requiredQty: number
  /** 현재고 */
  availableQty: number
  /** 부족수량 */
  shortageQty: number
}

export interface RiskTotals {
  totalPlans: number
  riskPlans: number
  overloadPlans: number
  shortagePlans: number
  overloadedWorkcenters: number
}

export type Severity = 'CRITICAL' | 'WARNING' | 'LOW'
export type Urgency = 'OVERDUE' | 'DUE_TODAY' | 'DUE_SOON' | 'NORMAL' | 'UNKNOWN'

export interface RiskSummaryFacts {
  windowStart: string | null
  windowEnd: string | null
  totals: RiskTotals
  /** Overloaded workcenters, peakLoadPercent descending. */
  workcenters: WorkcenterOverload[]
  affected: AffectedPlans
  shortages: ShortageComponent[]
  severity: Severity
  urgency: Urgency
  earliestDeliveryDate: string | null
  daysToEarliestDelivery: number | null
  /** Negative means the heaviest overloaded day has already passed. */
  daysToPeakOverload: number | null
}

export interface RecommendationItem {
  priority: number
  text: string
}

export interface RiskNarrative {
  /** 1. 영향(Impact)의 근본 원인 — starts with "[SEVERITY] " when the model complies. */
  rootCause: string
  /** 2. 영향받는 오더 및 작업장(WO) 및 심각도 */
  impactSummary: string
  /** 3. 해결 및 완화 권고 */
  recommendations: RecommendationItem[]
}

export interface RiskRecommendation {
  facts: RiskSummaryFacts
  narrative: RiskNarrative
  /** Figures the LLM invented; the backend discarded them. Debug only. */
  rejectedNumbers: string[]
}
