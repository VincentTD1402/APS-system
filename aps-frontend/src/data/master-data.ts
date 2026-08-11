// Master data — mirrors what G-System will push to APS.
// Values follow the spec `docs/specs/APS개발의뢰_20260707` and the FE mock guide
// at `docs/fe-mock-data-explanation-vi.md`.

export interface Equipment {
  code: string       // 설비ID
  wcCode: string     // parent workcenter
  nameKo: string
  stRate: number     // ST환산율
}

export interface WorkCenter {
  code: string
  nameKo: string
  defaultRuntimeMin: number   // 기본 가동시간 — spec always 480
  equipments: Equipment[]
}

export interface Item {
  code: string
  nameKo: string
  type: 'FINISHED' | 'RAW'
  wcCode?: string             // WC nơi item được sản xuất (FINISHED)
  standardStMin?: number      // Standard S/T phút/EA
}

export interface BomLine {
  parent: string              // finished item code
  child: string               // raw material code
  qtyPer: number              // số raw cho 1 finished EA
}

export interface InventoryLine {
  itemCode: string
  warehouse: string
  qty: number
}

export interface MpsOrder {
  id: string                  // order id (PO-... or WO-...)
  itemCode: string
  qty: number
  deliveryDate: string        // YYYY-MM-DD (납기)
  sourceType: 'MPS' | 'WO'
  workOrderNo: string | null  // set when sourceType === 'WO'
}

// ── Constants ─────────────────────────────────────────────────────────────────

// Today reference — matrix "walk backward until today" uses this floor.
export const MOCK_TODAY = '2026-08-01'

// Spec luôn dùng 480 phút / ngày cho 기본 가동시간
const DEFAULT_RUNTIME = 480

// ── Work centers + equipment ──────────────────────────────────────────────────
// 5 WC, mỗi WC có 1-2 equipment với ST환산율 khác nhau.
// Total daily runtime = Σ(defaultRuntime × stRate) — đây là capacity so sánh
// với minutes_loaded của ô matrix để quyết định overload.

export const WORK_CENTERS: WorkCenter[] = [
  {
    code: 'WC001-abqoweirupo', nameKo: '조립', defaultRuntimeMin: DEFAULT_RUNTIME,
    equipments: [
      { code: '설비001-1', wcCode: 'WC001', nameKo: '조립기 1', stRate: 0.80 },
      { code: '설비001-2', wcCode: 'WC001', nameKo: '조립기 2', stRate: 1.30 },
    ], // 480×0.8 + 480×1.3 = 1008
  },
  {
    code: 'WC002', nameKo: '사출', defaultRuntimeMin: DEFAULT_RUNTIME,
    equipments: [
      { code: '설비002-1', wcCode: 'WC002', nameKo: '사출기 1', stRate: 1.00 },
      { code: '설비002-2', wcCode: 'WC002', nameKo: '사출기 2', stRate: 1.10 },
    ], // 480 + 528 = 1008
  },
  {
    code: 'WC003', nameKo: '도장', defaultRuntimeMin: DEFAULT_RUNTIME,
    equipments: [
      { code: '설비003-1', wcCode: 'WC003', nameKo: '도장기 1', stRate: 0.90 },
      { code: '설비003-2', wcCode: 'WC003', nameKo: '도장기 2', stRate: 1.20 },
    ], // 432 + 576 = 1008
  },
  {
    code: 'WC004', nameKo: '검사', defaultRuntimeMin: DEFAULT_RUNTIME,
    equipments: [
      { code: '설비004-1', wcCode: 'WC004', nameKo: '검사기 1', stRate: 1.00 },
    ], // 480
  },
  {
    code: 'WC005', nameKo: '포장', defaultRuntimeMin: DEFAULT_RUNTIME,
    equipments: [
      { code: '설비005-1', wcCode: 'WC005', nameKo: '포장기 1', stRate: 0.80 },
      { code: '설비005-2', wcCode: 'WC005', nameKo: '포장기 2', stRate: 1.00 },
    ], // 384 + 480 = 864
  },
]

/** Tổng runtime (capacity) mỗi ngày của 1 WC = Σ(defaultRuntime × stRate). */
export function totalRuntimeMinOf(wc: WorkCenter): number {
  return wc.equipments.reduce((s, e) => s + wc.defaultRuntimeMin * e.stRate, 0)
}

// ── Items + routing ───────────────────────────────────────────────────────────
// Mỗi finished item chạy 1 WC với standard S/T phút/EA.
// Daily capacity theo EA = totalRuntime / standardSt.

export const ITEMS: Item[] = [
  { code: '제품1', nameKo: '제품1', type: 'FINISHED', wcCode: 'WC001', standardStMin: 6.00 },
  { code: '제품2', nameKo: '제품2', type: 'FINISHED', wcCode: 'WC002', standardStMin: 10.50 },
  { code: '제품3', nameKo: '제품3', type: 'FINISHED', wcCode: 'WC003', standardStMin: 18.33 },
  { code: '제품4', nameKo: '제품4', type: 'FINISHED', wcCode: 'WC004', standardStMin: 4.00 },
  { code: '제품5', nameKo: '제품5', type: 'FINISHED', wcCode: 'WC005', standardStMin: 8.00 },
  { code: '자재-A', nameKo: '자재-A', type: 'RAW' },
  { code: '자재-B', nameKo: '자재-B', type: 'RAW' },
]

// ── BOM ───────────────────────────────────────────────────────────────────────

export const BOM: BomLine[] = [
  { parent: '제품1', child: '자재-A', qtyPer: 2 },
  { parent: '제품2', child: '자재-A', qtyPer: 1 },
  { parent: '제품2', child: '자재-B', qtyPer: 3 },
  { parent: '제품3', child: '자재-B', qtyPer: 1 },
  { parent: '제품4', child: '자재-A', qtyPer: 1 },
  { parent: '제품5', child: '자재-B', qtyPer: 2 },
]

// ── Inventory ─────────────────────────────────────────────────────────────────
// Cân bằng cho demo:
// - 자재-A tổng 5300 → đủ cho toàn bộ nhu cầu A (không có A-shortage).
// - 자재-B tổng 3000 → thiếu B: chỉ PO-2026-003 và PO-2026-009 (제품2 cần B) bị thiếu.
// PO-2026-009 được thêm để tạo ô 🔴 (자재부족+부하초과) trên WC002 các ngày cuối.

export const INVENTORY: InventoryLine[] = [
  { itemCode: '자재-A', warehouse: 'WH01', qty: 3000 },
  { itemCode: '자재-A', warehouse: 'WH02', qty: 2300 },
  { itemCode: '자재-B', warehouse: 'WH01', qty: 2000 },
  { itemCode: '자재-B', warehouse: 'WH02', qty: 1000 },
]

// ── MPS orders + pending WOs ──────────────────────────────────────────────────
// 5 MPS đúng dòng 76-80 spec + 1 WO pending + 3 extra để lấp WC004/005.

export const MPS_ORDERS: MpsOrder[] = [
  { id: 'PO-2026-001', itemCode: '제품1', qty: 500,  deliveryDate: '2026-08-11', sourceType: 'MPS', workOrderNo: null },
  { id: 'PO-2026-002', itemCode: '제품1', qty: 1000, deliveryDate: '2026-08-15', sourceType: 'MPS', workOrderNo: null },
  { id: 'PO-2026-003', itemCode: '제품2', qty: 1200, deliveryDate: '2026-08-20', sourceType: 'MPS', workOrderNo: null },
  { id: 'PO-2026-004', itemCode: '제품3', qty: 800,  deliveryDate: '2026-08-19', sourceType: 'MPS', workOrderNo: null },
  { id: 'PO-2026-005', itemCode: '제품3', qty: 170,  deliveryDate: '2026-08-05', sourceType: 'MPS', workOrderNo: null },
  { id: 'PO-2026-006', itemCode: '제품4', qty: 300,  deliveryDate: '2026-08-08', sourceType: 'MPS', workOrderNo: null },
  { id: 'PO-2026-007', itemCode: '제품5', qty: 250,  deliveryDate: '2026-08-12', sourceType: 'MPS', workOrderNo: null },
  { id: 'PO-2026-008', itemCode: '제품4', qty: 400,  deliveryDate: '2026-08-22', sourceType: 'MPS', workOrderNo: null },
  // Đơn nhỏ 제품2 (200 EA) đè lên chuỗi cuối của PO-2026-003 (08-18..08-20)
  // → tạo overload + shortage cùng ngày → ô 🔴 자재부족+부하초과 trên WC002.
  { id: 'PO-2026-009', itemCode: '제품2', qty: 200,  deliveryDate: '2026-08-20', sourceType: 'MPS', workOrderNo: null },
  { id: 'WO-2026-0001', itemCode: '제품2', qty: 200, deliveryDate: '2026-08-04', sourceType: 'WO', workOrderNo: 'WO-2026-0001' },
]

// ── Helper lookups ────────────────────────────────────────────────────────────

export function findWc(code: string): WorkCenter | undefined {
  return WORK_CENTERS.find((w) => w.code === code)
}

export function findItem(code: string): Item | undefined {
  return ITEMS.find((i) => i.code === code)
}

export function bomOf(parent: string): BomLine[] {
  return BOM.filter((b) => b.parent === parent)
}

/** Tổng tồn kho aggregated across warehouses của 1 raw material. */
export function inventoryTotal(itemCode: string): number {
  return INVENTORY.filter((l) => l.itemCode === itemCode).reduce((s, l) => s + l.qty, 0)
}
