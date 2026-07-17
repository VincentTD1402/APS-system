export interface WorkCenter {
  code: string
  nameKo: string
  nameVi: string
  defaultRuntimeMin: number
  equipments: Equipment[]
  totalRuntimeMin: number
}

export interface Equipment {
  code: string
  wcCode: string
  nameKo: string
  nameVi: string
  stRate: number
}

export interface Item {
  code: string
  nameKo: string
  nameVi: string
  uom: string
}

export interface Routing {
  id: string
  itemCode: string
  stepNo: number
  wcCode: string
  processNameKo: string
  processNameVi: string
  standardStMin: number
}

export interface BomComponent {
  id: string
  parentItemCode: string
  childItemCode: string
  qtyPer: number
  scrapRate: number
}

export interface InventoryRow {
  id: string
  itemCode: string
  warehouseCode: string
  onHand: number
  asOfDate: string
}
