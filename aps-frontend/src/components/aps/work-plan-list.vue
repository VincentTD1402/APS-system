<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDragScroll } from '@/composables/use-drag-scroll'
import { useApsStore } from '@/stores/aps-store'
import BadgeTag from '@/components/aps/badge-tag.vue'
import type { WorkPlanRow, RiskKind } from '@/data/mock-scheduler'

const store = useApsStore()
const { t } = useI18n()

const emit = defineEmits<{
  select: [row: WorkPlanRow, key: string]
}>()

const selectedKey = ref<string | null>(null)

function selectRow(row: WorkPlanRow, idx: number) {
  const key = store.rowKey(row, idx)
  selectedKey.value = key
  store.selectRow(key)
  emit('select', row, key)
}

function onKeydown(e: KeyboardEvent, row: WorkPlanRow, idx: number) {
  if (e.key !== 'Enter' && e.key !== ' ') return
  e.preventDefault()
  selectRow(row, idx)
}

// ── Risk chip ─────────────────────────────────────────────────────────────────
// riskTypes là mảng. Chip hiển thị: normal | overload | shortage | both.
interface Chip { code: string; label: string }
function riskChip(rt: RiskKind[]): Chip {
  const hasOver = rt.includes('overload')
  const hasShort = rt.includes('material_short')
  if (hasOver && hasShort) return { code: 'both', label: t('risk.both') }
  if (hasOver) return { code: 'overload', label: t('risk.overload') }
  if (hasShort) return { code: 'shortage', label: t('risk.materialShort') }
  return { code: 'normal', label: t('risk.normal') }
}

// ── Custom vertical scrollbar ─────────────────────────────────────────────────
const scrollInner = ref<HTMLElement | null>(null)
const wpVTrack    = ref<HTMLElement | null>(null)
const wpVThumb    = ref<HTMLElement | null>(null)

let cleanupScroll: (() => void) | null = null

onMounted(() => {
  const el    = scrollInner.value!
  const track = wpVTrack.value!
  const thumb = wpVThumb.value!

  const { cleanup } = useDragScroll({
    scrollEl: el,
    track,
    thumb,
    axis: 'y',
  })
  cleanupScroll = cleanup
})

onUnmounted(() => {
  cleanupScroll?.()
})

// Format YYYY-MM-DD identity (đã đúng shape). Extract cho consistency.
function d(s: string): string { return s }

const rows = computed(() => store.filteredWp)
</script>

<template>
  <div class="wp-panel area-wp">
    <div class="wp-header">
      <div class="wp-title">
        <svg class="ic-list" aria-hidden="true"><use href="#ic-list"/></svg>
        {{ t('workPlanList.title') }}
      </div>
    </div>
    <div class="wp-subheader"><b>{{ rows.length }}</b> {{ t('workPlanList.unit') }}</div>
    <div class="wp-body">
      <div class="wp-scroll-inner" ref="scrollInner">
        <table class="wp-table">
          <thead>
            <tr>
              <th class="col-gear">
                <svg class="ic-gear" width="18" height="18" viewBox="0 0 20 20" aria-hidden="true"><use href="#ic-gear"/></svg>
              </th>
              <th>{{ t('workPlanList.col.workOrderNo') }}</th>
              <th>{{ t('workPlanList.col.tmpPlanNo') }}</th>
              <th class="col-num">{{ t('workPlanList.col.orderNo') }}</th>
              <th>{{ t('workPlanList.col.item') }}</th>
              <th>{{ t('workPlanList.col.wc') }}</th>
              <th>{{ t('workPlanList.col.process') }}</th>
              <th class="col-num">{{ t('workPlanList.col.planQty') }}</th>
              <th>{{ t('workPlanList.col.planStart') }}</th>
              <th>{{ t('workPlanList.col.planEnd') }}</th>
              <th>{{ t('workPlanList.col.deliveryDate') }}</th>
              <th>{{ t('workPlanList.col.sourceType') }}</th>
              <th>{{ t('workPlanList.col.riskType') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, i) in rows"
              :key="store.rowKey(row, i)"
              :class="{ selected: selectedKey === store.rowKey(row, i) }"
              :aria-selected="selectedKey === store.rowKey(row, i)"
              tabindex="0"
              role="row"
              @click="selectRow(row, i)"
              @keydown="onKeydown($event, row, i)"
            >
              <td class="col-gear">{{ i + 1 }}</td>
              <!-- Badge 3-state cạnh identifier chính: 대기중 / 해결됨 / 미해결 -->
              <td>
                {{ row.workOrderNo ?? '-' }}
                <BadgeTag
                  v-if="row.workOrderNo"
                  :state="store.badgeStateOf(row, store.rowKey(row, i))"
                />
              </td>
              <td>
                {{ row.tmpPlanNo ?? '-' }}
                <BadgeTag
                  v-if="!row.workOrderNo"
                  :state="store.badgeStateOf(row, store.rowKey(row, i))"
                />
              </td>
              <td class="col-num">{{ row.orderNo }}</td>
              <td>{{ row.itemName }}</td>
              <td>{{ row.workcenterName }}</td>
              <td>{{ row.procName }}</td>
              <td class="col-num">{{ row.plannedQty }}</td>
              <td>{{ d(row.planStart) }}</td>
              <td>{{ d(row.planEnd) }}</td>
              <td>{{ d(row.deliveryDate) }}</td>
              <td>{{ row.sourceType }}</td>
              <td>
                <span :class="`risk-chip r-${riskChip(row.riskTypes).code}`">
                  {{ riskChip(row.riskTypes).label }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="wp-vscroll">
        <div class="wp-vscroll-track" ref="wpVTrack">
          <div class="wp-vscroll-thumb" ref="wpVThumb"></div>
        </div>
      </div>
    </div>
  </div>
</template>

