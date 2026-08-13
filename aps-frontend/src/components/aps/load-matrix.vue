<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDragScroll } from '@/composables/use-drag-scroll'
import { useApsStore } from '@/stores/aps-store'
import type { LoadCellStatus, WorkPlanRow } from '@/data/mock-scheduler'

const store = useApsStore()
const { t } = useI18n()

// ── DOM refs ──────────────────────────────────────────────────────────────────
const fixedSide  = ref<HTMLElement | null>(null)
const scrollSide = ref<HTMLElement | null>(null)
const lmBody     = ref<HTMLElement | null>(null)
const vTrack     = ref<HTMLElement | null>(null)
const vThumb     = ref<HTMLElement | null>(null)
const hTrack     = ref<HTMLElement | null>(null)
const hThumb     = ref<HTMLElement | null>(null)

// ── Expand state ──────────────────────────────────────────────────────────────
// Set các WC đang expand (hiện equipment breakdown bên dưới).
const expandedWcs = ref<Set<string>>(new Set())
function toggleExpand(wcCode: string) {
  const s = new Set(expandedWcs.value)
  if (s.has(wcCode)) s.delete(wcCode)
  else s.add(wcCode)
  expandedWcs.value = s
}

// ── Cell status → CSS class (giữ class hiện có cho backward-compat) ──────────
const STATUS_CLASS: Record<LoadCellStatus, string> = {
  empty: 'cell-empty',
  normal: 'cell-normal',
  overload: 'cell-overload',
  'material-shortage': 'cell-shortage',
  urgent: 'cell-both',
}

interface WcRow {
  code: string
  name: string
  count: number
  sum: string
}

const wcRows = computed<WcRow[]>(() =>
  store.workCenters.map((w) => ({
    code: w.code,
    name: `${w.code} · ${w.nameKo}`,
    count: store.countByWc.get(w.code) ?? 0,
    sum: (store.qtyByWc.get(w.code) ?? 0).toLocaleString('en-US'),
  })),
)

// ── Flattened rows (WC + expanded per-order sub-rows) ────────────────────────
// Sub-row = 1 work order (작업지시번호 hoặc (임시)작업계획번호) đang schedule trên WC.
// Chỉ xuất hiện sau khi RUN (workPlans populated). Cells hiện qty của dailyPlans,
// tô màu theo riskTypes của order.
interface FlatRow {
  kind: 'wc' | 'order'
  key: string
  wc: WcRow
  plan?: WorkPlanRow
  planDailyIndex?: Map<string, number>  // date → qty (nhanh cho cell lookup)
}

const flatRows = computed<FlatRow[]>(() => {
  const out: FlatRow[] = []
  for (const row of wcRows.value) {
    out.push({ kind: 'wc', key: row.code, wc: row })
    if (expandedWcs.value.has(row.code)) {
      const plans = store.workPlans.filter((p) => p.workcenterNo === row.code)
      for (const p of plans) {
        const idx = new Map<string, number>()
        for (const dp of p.dailyPlans) idx.set(dp.date, dp.qty)
        out.push({ kind: 'order', key: `${row.code}::${p.id}`, wc: row, plan: p, planDailyIndex: idx })
      }
    }
  }
  return out
})

/**
 * CSS class cho ô sub-row tại 1 ngày.
 * Màu lấy từ aggregate cell status của (WC, date) đó — tức là chỉ overload khi
 * ngày đó có nhiều plan trùng và vượt capacity, chứ không paint cả plan.
 */
function orderCellClass(plan: WorkPlanRow, date: string, hasQty: boolean): string {
  if (!hasQty) return 'cell cell-empty'
  const c = store.loadCellIndex.get(`${plan.workcenterNo}::${date}`)
  const status = c?.status ?? 'normal'
  return `cell ${STATUS_CLASS[status]}`
}

// ── Aggregate cell (WC level) ────────────────────────────────────────────────
function cellFor(wc: string, date: string) {
  return store.loadCellIndex.get(`${wc}::${date}`)
}

function cellClass(wc: string, date: string): string {
  const c = cellFor(wc, date)
  const base = c ? `cell ${STATUS_CLASS[c.status]}` : 'cell cell-empty'
  const sel = store.cellSelection
  if (sel && sel.wc === wc && sel.date === date) return `${base} cell-selected`
  return base
}

function onCellClick(wc: string, date: string, dayIdx: number): void {
  const c = cellFor(wc, date)
  if (!c || c.status === 'empty') return
  store.setCellSelection({ wc, date, dayIdx })
}

// ── Scrollbar wiring ──────────────────────────────────────────────────────────
const H_PAD = 8
let cleanupV: (() => void) | null = null
let cleanupH: (() => void) | null = null

function onLmBodyWheel(e: WheelEvent) {
  const ss = scrollSide.value
  if (!ss) return
  const dx = e.deltaX || (e.shiftKey ? e.deltaY : 0)
  const dy = e.shiftKey ? 0 : e.deltaY
  let handled = false
  if (dx) { ss.scrollLeft += dx; handled = true }
  if (dy) { ss.scrollTop  += dy; handled = true }
  if (handled) e.preventDefault()
}

onMounted(() => {
  const ss = scrollSide.value!
  const fs = fixedSide.value!
  const lb = lmBody.value!
  const vt = vTrack.value!
  const vtb = vThumb.value!
  const ht = hTrack.value!
  const htb = hThumb.value!

  const v = useDragScroll({
    scrollEl: ss,
    track: vt,
    thumb: vtb,
    axis: 'y',
    syncPartner: fs,
  })
  cleanupV = v.cleanup

  const h = useDragScroll({
    scrollEl: ss,
    track: ht,
    thumb: htb,
    axis: 'x',
    pad: H_PAD,
  })
  cleanupH = h.cleanup

  lb.addEventListener('wheel', onLmBodyWheel, { passive: false })

  if (window.ResizeObserver) {
    const ro = new ResizeObserver(() => { v.update(); h.update() })
    ro.observe(ss)
    ;(ss as unknown as { _ro: ResizeObserver })._ro = ro
  }
})

onUnmounted(() => {
  cleanupV?.()
  cleanupH?.()
  const ss = scrollSide.value
  if (ss) {
    ss.removeEventListener('wheel', onLmBodyWheel)
    const ro = (ss as unknown as { _ro?: ResizeObserver })._ro
    ro?.disconnect()
  }
})

function shortDate(d: string): string {
  const [, m, dd] = d.split('-')
  return `${Number(m)}/${Number(dd)}`
}
</script>

<template>
  <div class="lm-panel area-lm">
    <div class="lm-header">
      <div class="lm-title">
        <svg class="ic-clock" aria-hidden="true"><use href="#ic-clock"/></svg>
        {{ t('loadMatrix.title') }}
      </div>
      <div class="lm-legend">
        <span class="lg-item"><i class="sw sw-normal"></i>{{ t('loadMatrix.legend.normal') }}</span>
        <span class="lg-item"><i class="sw sw-shortage"></i>{{ t('loadMatrix.legend.materialShort') }}</span>
        <span class="lg-item"><i class="sw sw-overload"></i>{{ t('loadMatrix.legend.overload') }}</span>
        <span class="lg-item"><i class="sw sw-both"></i>{{ t('loadMatrix.legend.both') }}</span>
        <span class="lg-item"><i class="sw sw-unassigned"></i>{{ t('loadMatrix.legend.empty') }}</span>
      </div>
    </div>

    <div class="lm-body" ref="lmBody">
      <!-- Left: 3 fixed cols -->
      <div class="lm-fixed-side" ref="fixedSide">
        <table class="lm-table lm-t-fixed">
          <thead>
            <tr>
              <th class="col-wc">{{ t('loadMatrix.col.wc') }}</th>
              <th class="col-count col-num">{{ t('loadMatrix.col.count') }}</th>
              <th class="col-sum col-num">{{ t('loadMatrix.col.qtySum') }}</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="row in flatRows" :key="row.key">
              <!-- WC row (expandable, click toggles) -->
              <tr v-if="row.kind === 'wc'" class="lm-row-wc" @click="toggleExpand(row.wc.code)">
                <td class="col-wc">{{ row.wc.name }}</td>
                <td class="col-count col-num">{{ row.wc.count }}</td>
                <td class="col-sum col-num">{{ row.wc.sum }}</td>
              </tr>
              <!-- Order sub-row: 1 row per (임시)작업계획번호/작업지시번호 -->
              <tr v-else class="lm-row-order">
                <td class="col-wc lm-order-name">
                  <span class="lm-order-id">{{ row.plan!.workOrderNo ?? row.plan!.tmpPlanNo ?? '-' }}</span>
                  <span class="lm-order-item">{{ row.plan!.itemName }}</span>
                </td>
                <td class="col-count col-num">1</td>
                <td class="col-sum col-num">{{ row.plan!.plannedQty.toLocaleString('en-US') }}</td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <!-- Right: date cols -->
      <div class="lm-scroll-side" ref="scrollSide">
        <div class="lm-scroll-cap"></div>
        <table class="lm-table lm-t-dates">
          <thead>
            <tr>
              <th v-for="d in store.dates" :key="d" class="col-date">{{ shortDate(d) }}</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="row in flatRows" :key="row.key">
              <!-- WC aggregate cells: color only, no number -->
              <tr v-if="row.kind === 'wc'" class="lm-row-wc">
                <td
                  v-for="(d, ci) in store.dates"
                  :key="ci"
                  :class="cellClass(row.wc.code, d)"
                  @click="onCellClick(row.wc.code, d, ci)"
                  style="cursor: pointer"
                >
                  <span class="chip-cell"></span>
                </td>
              </tr>
              <!-- Order sub-row cells: qty per day; empty on days ngoài lịch order -->
              <tr v-else class="lm-row-order">
                <td
                  v-for="(d, ci) in store.dates"
                  :key="ci"
                  :class="orderCellClass(row.plan!, d, row.planDailyIndex!.has(d))"
                >
                  <span class="chip-cell chip-order">
                    {{ row.planDailyIndex!.get(d) ?? '' }}
                  </span>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <!-- Custom vertical scrollbar -->
      <div class="lm-vscroll">
        <div class="lm-vscroll-track" ref="vTrack">
          <div class="lm-vscroll-thumb" ref="vThumb"></div>
        </div>
      </div>
    </div>

    <!-- Footer row: 합계 (left) + custom horizontal scrollbar (right) -->
    <div class="lm-footer-row">
      <div class="lm-footer-fixed">
        <span class="ff-wc">{{ t('loadMatrix.total') }}</span>
        <span class="ff-count">{{ store.totalCount }}</span>
        <span class="ff-sum">{{ store.totalSum }}</span>
      </div>
      <div class="lm-hscroll">
        <div class="lm-hscroll-track" ref="hTrack">
          <div class="lm-hscroll-thumb" ref="hThumb"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.lm-row-wc { cursor: pointer; }
.lm-row-order { background: #fafafa; }
.lm-order-name {
  font-size: 11px;
  color: #48494d;
  padding-left: 18px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.lm-order-id { font-weight: 500; margin-right: 6px; }
.lm-order-item { color: #7a7a7a; }
.chip-order {
  font-size: 11px;
  font-weight: 500;
}
</style>
