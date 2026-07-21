export interface WorkCenter {
  code: string
  nameKo: string
  // nameVi bỏ khỏi BE (G-System chỉ có Korean) — giữ optional để tương thích view cũ.
  nameVi?: string | null
  defaultRuntimeMin: number
  equipments: Equipment[]
  totalRuntimeMin: number
}

export interface Equipment {
  code: string
  wcCode: string
  nameKo: string
  nameVi?: string | null
  stRate: number
}

export interface Item {
  code: string
  nameKo: string
  nameVi?: string | null
  uom: string
}

export interface Routing {
  id: string
  itemCode: string
  stepNo: number
  wcCode: string
  processNameKo: string
  processNameVi?: string | null
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
