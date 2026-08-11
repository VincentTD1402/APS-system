import { http } from './http'
import type { RiskRecommendation } from '@/types/llm'

// The AI제안 panel summarises the whole work plan list currently on screen, so
// the query mirrors GET /work-plan/list. Only the three filters the backend
// actually supports are sent; 사업부/계획구분/Rev./처리상태/담당자/부서 have no
// server-side equivalent yet.
export interface RiskSummaryParams {
  dateFrom?: string // YYYY-MM-DD
  dateTo?: string
  /** APS전표번호 — matched against tmp_plan_no / work_order_no / order_no. */
  planNo?: string
  /** Skip the server cache and re-run the LLM. Use after the plan data changed. */
  refresh?: boolean
}

// The backend reads an empty string as a real filter value and would then match
// nothing, so blank fields must be dropped rather than sent as "".
function compactParams(p: RiskSummaryParams): Record<string, string> {
  const out: Record<string, string> = {}
  if (p.dateFrom) out.date_from = p.dateFrom
  if (p.dateTo) out.date_to = p.dateTo
  if (p.planNo) out.plan_no = p.planNo
  if (p.refresh) out.refresh = 'true'
  return out
}

export async function fetchRiskSummary(
  params: RiskSummaryParams = {}
): Promise<RiskRecommendation> {
  const { data } = await http.get<RiskRecommendation>('/llm/work-plan-risk-summary', {
    params: compactParams(params),
    // Generating the narrative takes a couple of seconds, and a cold call on a
    // large plan can take longer — well past the client's 30s default.
    timeout: 60_000,
  })
  return data
}
