export type RiskType = 'NORMAL' | 'MATERIAL_SHORT' | 'OVERLOAD' | 'MATERIAL_AND_OVERLOAD'

export type LoadCellStatus =
  | 'EMPTY'
  | 'NORMAL'
  | 'MATERIAL_SHORT'
  | 'OVERLOAD'
  | 'OVERLOAD_AND_MATERIAL_SHORT'

export type MpsStatus = 'DRAFT' | 'CONFIRMED' | 'CANCELLED'

export type WorkOrderStatus = 'PENDING' | 'DONE'

export type WorkPlanSourceType = 'FROM_WORK_ORDER' | 'FROM_MPS'

export type ErpOutboxAction = 'CREATE_WORK_ORDER' | 'CREATE_PURCHASE_REQUEST'
export type ErpOutboxStatus = 'PENDING' | 'PUSHED' | 'FAILED'

export type InventoryTxType = 'INBOUND_ACTUAL' | 'INBOUND_PLANNED' | 'OUTBOUND_PLANNED'
