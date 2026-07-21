import { http } from './http'
import type { ErpOutboxRow } from '@/types/planning'

export async function createPurchaseRequest(
  planId: string,
  qty: number,
  note: string
): Promise<ErpOutboxRow> {
  const { data } = await http.post<ErpOutboxRow>('/erp/purchase-requests', { planId, qty, note })
  return data
}

export async function createWorkOrder(planId: string): Promise<ErpOutboxRow> {
  const { data } = await http.post<ErpOutboxRow>('/erp/work-orders', { planId })
  return data
}
