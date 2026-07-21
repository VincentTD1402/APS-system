import { http } from './http'
import type { Mps, WorkOrder } from '@/types/planning'

// BE `id` int → FE string.
function stringifyId<T extends { id: number | string }>(row: T): T {
  return { ...row, id: String(row.id) } as T
}

// BE `mpsId` cũng int → FE string (nullable).
function stringifyWorkOrder(row: WorkOrder & { mpsId: string | number | null }): WorkOrder {
  return {
    ...row,
    id: String(row.id),
    mpsId: row.mpsId == null ? null : String(row.mpsId),
  }
}

// BE `WorkOrder.status` = PLANNED/SENT/CONFIRMED/FAILED → FE enum PENDING/DONE.
function mapWorkOrderStatus(status: string): 'PENDING' | 'DONE' {
  return status === 'CONFIRMED' ? 'DONE' : 'PENDING'
}

export async function fetchMps(): Promise<Mps[]> {
  const { data } = await http.get<Mps[]>('/planning/mps')
  return data.map(stringifyId)
}

export async function fetchWorkOrders(): Promise<WorkOrder[]> {
  const { data } = await http.get<Array<WorkOrder & { mpsId: string | number | null }>>(
    '/planning/work-orders'
  )
  return data.map((row) => ({
    ...stringifyWorkOrder(row),
    status: mapWorkOrderStatus(row.status),
  }))
}
