import { http } from './http'
import type { WorkCenter, Item, Routing, BomComponent, InventoryRow, MaterialShortageRow } from '@/types/master'

// BE trả `id` là number cho routing/bom/inventory; FE type yêu cầu string → convert boundary.
function stringifyId<T extends { id: number | string }>(row: T): T {
  return { ...row, id: String(row.id) } as T
}

export async function fetchWorkCenters(): Promise<WorkCenter[]> {
  const { data } = await http.get<WorkCenter[]>('/master/work-centers')
  return data
}

export async function fetchItems(): Promise<Item[]> {
  const { data } = await http.get<Item[]>('/master/items')
  return data
}

export async function fetchRoutings(): Promise<Routing[]> {
  const { data } = await http.get<Routing[]>('/master/routings')
  return data.map(stringifyId)
}

export async function fetchBom(): Promise<BomComponent[]> {
  const { data } = await http.get<BomComponent[]>('/master/bom')
  return data.map(stringifyId)
}

export async function fetchInventory(): Promise<InventoryRow[]> {
  const { data } = await http.get<InventoryRow[]>('/master/inventory')
  return data.map(stringifyId)
}

// Raw-material components (BOM children) a product/semi-product needs, with
// required/available/shortage — one plan can have several materials.
export async function fetchMaterialShortageByParent(parentItemNo: string): Promise<MaterialShortageRow[]> {
  const { data } = await http.get<MaterialShortageRow[]>('/material-shortage', { params: { parentItemNo } })
  return data
}

// Full list — used by the APS work-plan view to build per-plan shortage breakdown
// after /aps/run or /aps/adjust (those endpoints only return the aggregate shortageQty).
export async function fetchMaterialShortages(): Promise<MaterialShortageRow[]> {
  const { data } = await http.get<MaterialShortageRow[]>('/material-shortage')
  return data
}

// Wipe + rewrite aps_material_shortage (required/available/shortage per component) —
// /aps/adjust doesn't call this, so a post-purchase-request refresh needs it explicitly.
export async function rebuildMaterialShortage(): Promise<void> {
  await http.post('/material-shortage/rebuild')
}
