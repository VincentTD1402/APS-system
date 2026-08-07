import { http } from './http'
import type { ErpOutboxRow } from '@/types/planning'
import type { PendingPurchaseLine } from '@/stores/aps-store'

export async function createPurchaseRequest(
  planId: string,
  note: string,
  lines: PendingPurchaseLine[]
): Promise<ErpOutboxRow> {
  const { data } = await http.post<ErpOutboxRow>('/erp/purchase-requests', {
    planId,
    note,
    lines: lines.map((l) => ({ itemNo: l.itemNo, qty: l.qty })),
  })
  return data
}

export async function createWorkOrder(planId: string): Promise<ErpOutboxRow> {
  const { data } = await http.post<ErpOutboxRow>('/erp/work-orders', { planId })
  return data
}
