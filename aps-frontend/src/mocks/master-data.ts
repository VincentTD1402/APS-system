import type {
  WorkCenter,
  Equipment,
  Item,
  Routing,
  BomComponent,
  InventoryRow,
} from '@/types/master'

export const MOCK_TODAY = '2026-08-01'

export const MOCK_WORK_CENTERS: WorkCenter[] = [
  {
    code: 'WC001',
    nameKo: 'WC001 조립',
    nameVi: 'WC001 Lắp ráp',
    defaultRuntimeMin: 480,
    equipments: [],
    totalRuntimeMin: 1008,
  },
  {
    code: 'WC002',
    nameKo: 'WC002 사출',
    nameVi: 'WC002 Ép',
    defaultRuntimeMin: 480,
    equipments: [],
    totalRuntimeMin: 1008,
  },
  {
    code: 'WC003',
    nameKo: 'WC003 도장',
    nameVi: 'WC003 Sơn',
    defaultRuntimeMin: 480,
    equipments: [],
    totalRuntimeMin: 1008,
  },
]

export const MOCK_EQUIPMENTS: Equipment[] = [
  { code: '설비001-1', wcCode: 'WC001', nameKo: '설비001-1', nameVi: 'Máy 001-1', stRate: 0.8 },
  { code: '설비001-2', wcCode: 'WC001', nameKo: '설비001-2', nameVi: 'Máy 001-2', stRate: 1.3 },
  { code: '설비002-1', wcCode: 'WC002', nameKo: '설비002-1', nameVi: 'Máy 002-1', stRate: 1.0 },
  { code: '설비002-2', wcCode: 'WC002', nameKo: '설비002-2', nameVi: 'Máy 002-2', stRate: 1.1 },
  { code: '설비003-1', wcCode: 'WC003', nameKo: '설비003-1', nameVi: 'Máy 003-1', stRate: 0.9 },
  { code: '설비003-2', wcCode: 'WC003', nameKo: '설비003-2', nameVi: 'Máy 003-2', stRate: 1.2 },
]

for (const eq of MOCK_EQUIPMENTS) {
  const wc = MOCK_WORK_CENTERS.find((w) => w.code === eq.wcCode)
  wc?.equipments.push(eq)
}

export const MOCK_ITEMS: Item[] = [
  { code: '제품1', nameKo: '제품1', nameVi: 'Sản phẩm 1', uom: 'EA' },
  { code: '제품2', nameKo: '제품2', nameVi: 'Sản phẩm 2', uom: 'EA' },
  { code: '제품3', nameKo: '제품3', nameVi: 'Sản phẩm 3', uom: 'EA' },
  { code: '자재-A', nameKo: '자재-A', nameVi: 'Vật liệu A', uom: 'EA' },
  { code: '자재-B', nameKo: '자재-B', nameVi: 'Vật liệu B', uom: 'EA' },
]

export const MOCK_ROUTINGS: Routing[] = [
  {
    id: 'r1',
    itemCode: '제품1',
    stepNo: 1,
    wcCode: 'WC001',
    processNameKo: '조립',
    processNameVi: 'Lắp ráp',
    standardStMin: 6.0,
  },
  {
    id: 'r2',
    itemCode: '제품2',
    stepNo: 1,
    wcCode: 'WC002',
    processNameKo: '사출',
    processNameVi: 'Ép',
    standardStMin: 10.5,
  },
  {
    id: 'r3',
    itemCode: '제품3',
    stepNo: 1,
    wcCode: 'WC003',
    processNameKo: '도장',
    processNameVi: 'Sơn',
    standardStMin: 18.33,
  },
]

export const MOCK_BOM: BomComponent[] = [
  { id: 'b1', parentItemCode: '제품1', childItemCode: '자재-A', qtyPer: 2, scrapRate: 0 },
  { id: 'b2', parentItemCode: '제품2', childItemCode: '자재-A', qtyPer: 1, scrapRate: 0 },
  { id: 'b3', parentItemCode: '제품2', childItemCode: '자재-B', qtyPer: 3, scrapRate: 0 },
  { id: 'b4', parentItemCode: '제품3', childItemCode: '자재-B', qtyPer: 1, scrapRate: 0 },
]

// Inventory tuned so chỉ MPS-3 (제품2 1200 EA, delivery 08-20) short — không phải mọi plan.
// Demand tổng (theo thứ tự delivery_date):
//   자재-A: WO(200) + MPS-1(1000) + MPS-2(2000) + MPS-3(1200) = 4400
//   자재-B: WO(600) + MPS-5(170) + MPS-4(800) + MPS-3(3600) = 5170
// Stock cấp đủ trước MPS-3, MPS-3 sẽ thiếu (chấp nhận được để demo 구매요청).
export const MOCK_INVENTORY: InventoryRow[] = [
  { id: 'i1', itemCode: '자재-A', warehouseCode: 'WH01', onHand: 2000, asOfDate: MOCK_TODAY },
  { id: 'i2', itemCode: '자재-A', warehouseCode: 'WH02', onHand: 1600, asOfDate: MOCK_TODAY },
  { id: 'i3', itemCode: '자재-B', warehouseCode: 'WH01', onHand: 1200, asOfDate: MOCK_TODAY },
  { id: 'i4', itemCode: '자재-B', warehouseCode: 'WH02', onHand: 800, asOfDate: MOCK_TODAY },
]
