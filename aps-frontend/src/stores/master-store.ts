import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { WorkCenter, Item, Routing, BomComponent, InventoryRow } from '@/types/master'
import * as masterApi from '@/api/master'

// Cache master data — load 1 lần rồi share qua các view (Work Center list, Item list,
// BOM, Inventory, filter bar, load matrix, ...). Gọi ensureLoaded() ở component onMounted.
export const useMasterStore = defineStore('master', () => {
  const workCenters = ref<WorkCenter[]>([])
  const items = ref<Item[]>([])
  const routings = ref<Routing[]>([])
  const bom = ref<BomComponent[]>([])
  const inventory = ref<InventoryRow[]>([])

  const loaded = ref(false)
  const loading = ref(false)

  async function ensureLoaded(): Promise<void> {
    if (loaded.value || loading.value) return
    loading.value = true
    try {
      const [wc, it, rt, bm, iv] = await Promise.all([
        masterApi.fetchWorkCenters(),
        masterApi.fetchItems(),
        masterApi.fetchRoutings(),
        masterApi.fetchBom(),
        masterApi.fetchInventory(),
      ])
      workCenters.value = wc
      items.value = it
      routings.value = rt
      bom.value = bm
      inventory.value = iv
      loaded.value = true
    } finally {
      loading.value = false
    }
  }

  async function reload(): Promise<void> {
    loaded.value = false
    await ensureLoaded()
  }

  return { workCenters, items, routings, bom, inventory, loaded, loading, ensureLoaded, reload }
})
