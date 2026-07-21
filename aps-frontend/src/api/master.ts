import { http } from './http'
import type { WorkCenter, Item, Routing, BomComponent, InventoryRow } from '@/types/master'

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
