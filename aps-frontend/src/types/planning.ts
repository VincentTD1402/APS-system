import type {
  MpsStatus,
  WorkOrderStatus,
  WorkPlanSourceType,
  RiskType,
  LoadCellStatus,
  ErpOutboxAction,
  ErpOutboxStatus,
} from './enums'

export interface Mps {
  id: string
  orderNo: string
  itemCode: string
  planQty: number
  endDate: string
  workStartDate: string | null
  workEndDate: string | null
  status: MpsStatus
}

export interface WorkOrder {
  id: string
  woNo: string
  mpsId: string | null
  itemCode: string
  wcCode: string
  planQty: number
  planStartDate: string
  planEndDate: string
  status: WorkOrderStatus
}

export interface WorkPlanDaily {
  date: string
  qty: number
  minutes: number
}

export interface WorkPlan {
  id: string
  runId: string
  sourceType: WorkPlanSourceType
  workOrderNo: string | null
  tmpPlanNo: string | null
  orderNo: string
  itemCode: string
  itemNameKo: string
  itemNameVi: string
  wcCode: string
  wcName: string | null
  processNameKo: string
  processNameVi: string
  planQty: number
  planStartDate: string
  planEndDate: string
  deliveryDate: string
  riskType: RiskType
  shortageQty: number
  adjusted: boolean
  originalStart: string | null
  originalEnd: string | null
  dailyPlans: WorkPlanDaily[]
}

export interface LoadCell {
  wcCode: string
  wcName: string | null
  cellDate: string
  minutesLoaded: number
  minutesCapacity: number
  status: LoadCellStatus
}

export interface ApsRun {
  id: string
  startedAt: string
  finishedAt: string
}

export interface ErpOutboxRow {
  id: string
  runId: string | null
  action: ErpOutboxAction
  payload: Record<string, unknown>
  status: ErpOutboxStatus
  createdAt: string
  pushedAt: string | null
  error: string | null
}
