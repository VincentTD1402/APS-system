<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useDragScroll } from '@/composables/use-drag-scroll'
import { useApsStore } from '@/stores/aps-store'
import BadgeTag from '@/components/aps/badge-tag.vue'
import type { WorkPlanRow, RiskKind } from '@/data/mock-scheduler'

const store = useApsStore()

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
  if (hasOver && hasShort) return { code: 'both', label: '자재부족+부하초과' }
  if (hasOver) return { code: 'overload', label: '부하초과' }
  if (hasShort) return { code: 'shortage', label: '자재부족' }
  return { code: 'normal', label: '정상' }
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
        작업계획 리스트
      </div>
    </div>
    <div class="wp-subheader"><b>{{ rows.length }}</b> 건</div>
    <div class="wp-body">
      <div class="wp-scroll-inner" ref="scrollInner">
        <table class="wp-table">
          <thead>
            <tr>
              <th class="col-gear">
                <svg class="ic-gear" width="18" height="18" viewBox="0 0 20 20" aria-hidden="true"><use href="#ic-gear"/></svg>
              </th>
              <th>작업지시번호</th>
              <th>(임시)작업계획번호</th>
              <th class="col-num">오더</th>
              <th>품목</th>
              <th>워크센터</th>
              <th>공정</th>
              <th class="col-num">계획수량</th>
              <th>계획시작</th>
              <th>계획완료</th>
              <th>납기일자</th>
              <th>리스트유형</th>
              <th>리스크유형</th>
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
              <td>{{ row.workcenterNo }}</td>
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

