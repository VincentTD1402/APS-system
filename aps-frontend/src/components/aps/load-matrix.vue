<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useDragScroll } from '@/composables/use-drag-scroll'
import { useApsStore } from '@/stores/aps-store'
<<<<<<< HEAD
import { computed } from 'vue'
import dayjs from 'dayjs'
import type { LoadCellStatus } from '@/types/enums'
=======
import type { LoadCellStatus, WorkPlanRow } from '@/data/mock-scheduler'
>>>>>>> 0a34f17 (feat(fe): rebuild APS view from XD design with interactive flow)

const store = useApsStore()
<<<<<<< HEAD

// dateFrom/dateTo (filter-bar) pin the exact column span when set — this is
// a WC×day calendar view, so "chosen date window" is the natural read,
// unlike plan-detail-matrix (per-plan schedule, which must NOT be pinned to
// the completion-date filter — see that component). Falls back to the actual
// loaded schedule (min..max cellDate from /aps/run) when no filter is set,
// not a hardcoded month — aps_daily_plan's real window varies per run/
// backward-fill anchor and previously missed most of it, making workcenters
// look empty.
const dateRange = computed(() => {
  const { dateFrom, dateTo } = store.filter
  const cellDates = store.loadCells.map((c) => c.cellDate)
  const start = dateFrom
    ? dayjs(dateFrom)
    : cellDates.length ? dayjs(cellDates.reduce((a, b) => (a < b ? a : b))) : dayjs()
  const end = dateTo
    ? dayjs(dateTo)
    : cellDates.length ? dayjs(cellDates.reduce((a, b) => (a > b ? a : b))) : start.add(30, 'day')

  const dates: string[] = []
  let d = start
  while (!d.isAfter(end)) {
    dates.push(d.format('YYYY-MM-DD'))
    d = d.add(1, 'day')
=======

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
>>>>>>> 0a34f17 (feat(fe): rebuild APS view from XD design with interactive flow)
  }
  return out
})

<<<<<<< HEAD
// Only workcenters that actually appear in this run's loadCells — a workcenter
// with zero aps_daily_plan rows has nothing to show and only pads the grid.
const activeWorkCenters = computed(() => {
  const byCode = new Map<string, string | null>()
  for (const c of store.loadCells) if (!byCode.has(c.wcCode)) byCode.set(c.wcCode, c.wcName)
  return [...byCode.entries()]
    .map(([code, name]) => ({ code, name }))
    .sort((a, b) => a.code.localeCompare(b.code))
})

// CSS Grid instead of an HTML table — a table's row/cell layout (baseline
// alignment, inline-block whitespace gaps between elements) is a classic
// source of uneven-looking grids; a real grid keeps every cell an identical
// size with no such quirks, at any column count.
// wc-name column wide enough for "WS71 · WC-001"-style labels (was 88px —
// too narrow, clipped the text). Date columns always fill the remaining
// 100% of the panel width evenly (1fr each, min 24px) — by explicit choice,
// accepting that with few date columns each cell will be wider than tall.
const gridTemplateColumns = computed(() => `140px repeat(${dateRange.value.length}, minmax(24px, 1fr))`)

const cellIndex = computed(() => {
  const idx = new Map<string, LoadCellStatus>()
  for (const c of store.loadCells) idx.set(`${c.wcCode}|${c.cellDate}`, c.status)
  return idx
})
=======
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
>>>>>>> 0a34f17 (feat(fe): rebuild APS view from XD design with interactive flow)

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
        부하내역
      </div>
      <div class="lm-legend">
        <span class="lg-item"><i class="sw sw-normal"></i>정상</span>
        <span class="lg-item"><i class="sw sw-shortage"></i>자재부족</span>
        <span class="lg-item"><i class="sw sw-overload"></i>부하초과</span>
        <span class="lg-item"><i class="sw sw-both"></i>자재부족+부하초과</span>
        <span class="lg-item"><i class="sw sw-unassigned"></i>미배정</span>
      </div>
    </div>
<<<<<<< HEAD
    <div class="matrix-scroll">
      <div class="matrix-grid" :style="{ gridTemplateColumns }">
        <div class="grid-cell wc-col-head">WC</div>
        <div v-for="d in dateRange" :key="`h-${d}`" class="grid-cell date-col-head">{{ shortDate(d) }}</div>
        <template v-for="wc in activeWorkCenters" :key="wc.code">
          <div class="grid-cell wc-name">{{ wc.code }} · {{ wc.name }}</div>
          <div
            v-for="d in dateRange"
            :key="`${wc.code}-${d}`"
            class="grid-cell cell-slot"
          >
            <div
              :class="cellClass(wc.code, d)"
              :title="cellTitle(wc.code, d)"
              @click="onCellClick(wc.code, d)"
            />
          </div>
        </template>
=======

    <div class="lm-body" ref="lmBody">
      <!-- Left: 3 fixed cols -->
      <div class="lm-fixed-side" ref="fixedSide">
        <table class="lm-table lm-t-fixed">
          <thead>
            <tr>
              <th class="col-wc">워크센터</th>
              <th class="col-count col-num">지시건수</th>
              <th class="col-sum col-num">지시량계</th>
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
        <span class="ff-wc">합계</span>
        <span class="ff-count">{{ store.totalCount }}</span>
        <span class="ff-sum">{{ store.totalSum }}</span>
      </div>
      <div class="lm-hscroll">
        <div class="lm-hscroll-track" ref="hTrack">
          <div class="lm-hscroll-thumb" ref="hThumb"></div>
        </div>
>>>>>>> 0a34f17 (feat(fe): rebuild APS view from XD design with interactive flow)
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
<<<<<<< HEAD
  color: var(--p-text-muted-color);
  margin-top: 2px;
}
.legend {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: var(--p-text-muted-color);
  flex-wrap: wrap;
}
.legend .dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
  margin-right: 4px;
  vertical-align: middle;
}
.legend .dot.normal {
  background: var(--aps-ok);
}
.legend .dot.material-short {
  background: var(--aps-mat);
}
.legend .dot.overload {
  background: var(--aps-cap);
}
.legend .dot.both {
  background: var(--aps-crit);
}
.legend .dot.empty {
  border: 1px dashed rgba(128, 128, 128, 0.6);
}
.matrix-scroll {
  overflow: auto;
  max-height: 280px; /* cap chiều cao — nhiều WC thì scroll dọc, giữ header sticky */
  padding: 0px 14px 10px;
  margin-top: 10px;
}
.matrix-scroll thead th {
  position: sticky;
  top: 0;
  background: var(--p-content-background);
  z-index: 1;
}
/* CSS Grid: every column is an explicit track — 140px for the WC name
   column, then a 1fr (min 24px) track per date column (see
   gridTemplateColumns above), so date columns always share 100% of the
   panel's width evenly — by explicit choice, few columns means each is
   wider than tall. display:grid (not inline-grid) is required for the 1fr
   tracks to resolve against the full container width instead of shrinking
   to content. overflow-x above scrolls once min-width (24px/col) is hit
   with many columns. */
.matrix-grid {
  display: grid;
  gap: 2px;
  grid-auto-rows: 24px;
}
.grid-cell {
  display: flex;
  align-items: center;
  overflow: hidden;
}
.wc-col-head,
.date-col-head {
  font-family: var(--aps-mono);
  color: var(--p-text-muted-color);
  font-size: 10px;
  font-weight: 500;
  justify-content: center;
}
.wc-col-head {
  justify-content: flex-start;
  font-size: 11px;
  font-weight: 600;
}
.wc-name {
  font-family: var(--aps-mono);
  font-size: 12px;
  font-weight: 700;
  color: var(--p-text-color);
  white-space: nowrap;
  text-overflow: ellipsis;
  padding-right: 8px;
}
.cell-slot {
  justify-content: center;
=======
  font-weight: 500;
>>>>>>> 0a34f17 (feat(fe): rebuild APS view from XD design with interactive flow)
}
</style>
