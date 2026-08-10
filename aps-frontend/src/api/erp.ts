import { http } from './http'
import type { ErpOutboxRow } from '@/types/planning'

// Local shape cho purchase request line (không dùng store, tránh phụ thuộc vòng).
interface PurchaseRequestLine {
  itemNo: string
  qty: number
}

export async function createPurchaseRequest(
  planId: string,
  note: string,
  lines: PurchaseRequestLine[]
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
