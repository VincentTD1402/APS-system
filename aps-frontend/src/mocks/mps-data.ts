import type { Mps, WorkOrder } from '@/types/planning'

export const MOCK_MPS: Mps[] = [
  {
    id: 'mps-1',
    orderNo: 'PO-2026-001',
    itemCode: '제품1',
    planQty: 500,
    endDate: '2026-08-11',
    workStartDate: '2026-08-09',
    workEndDate: '2026-08-11',
    status: 'DRAFT',
  },
  {
    id: 'mps-2',
    orderNo: 'PO-2026-002',
    itemCode: '제품1',
    planQty: 1000,
    endDate: '2026-08-15',
    workStartDate: '2026-08-10',
    workEndDate: '2026-08-15',
    status: 'DRAFT',
  },
  {
    id: 'mps-3',
    orderNo: 'PO-2026-003',
    itemCode: '제품2',
    planQty: 1200,
    endDate: '2026-08-20',
    workStartDate: '2026-08-08',
    workEndDate: '2026-08-20',
    status: 'DRAFT',
  },
  {
    id: 'mps-4',
    orderNo: 'PO-2026-004',
    itemCode: '제품3',
    planQty: 800,
    endDate: '2026-08-19',
    workStartDate: '2026-08-04',
    workEndDate: '2026-08-19',
    status: 'DRAFT',
  },
  {
    id: 'mps-5',
    orderNo: 'PO-2026-005',
    itemCode: '제품3',
    planQty: 170,
    endDate: '2026-08-05',
    workStartDate: '2026-08-02',
    workEndDate: '2026-08-05',
    status: 'DRAFT',
  },
]

export const MOCK_WORK_ORDERS: WorkOrder[] = [
  {
    id: 'wo-1',
    woNo: 'WO-2026-0001',
    mpsId: null,
    itemCode: '제품2',
    wcCode: 'WC002',
    planQty: 200,
    planStartDate: '2026-08-02',
    planEndDate: '2026-08-04',
    status: 'PENDING',
  },
]
