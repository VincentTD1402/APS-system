<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useApsStore } from '@/stores/aps-store'
import { computed } from 'vue'
import dayjs from 'dayjs'
import type { LoadCellStatus } from '@/types/enums'

const { t } = useI18n()
const store = useApsStore()

// Span the actual loaded schedule (min..max cellDate from /aps/run), not a
// hardcoded month — aps_daily_plan's real window varies per run/backward-fill
// anchor and previously missed most of it, making workcenters look empty.
const dateRange = computed(() => {
  const cellDates = store.loadCells.map((c) => c.cellDate)
  const start = cellDates.length ? dayjs(cellDates.reduce((a, b) => (a < b ? a : b))) : dayjs()
  const end = cellDates.length
    ? dayjs(cellDates.reduce((a, b) => (a > b ? a : b)))
    : start.add(30, 'day')

  const dates: string[] = []
  let d = start
  while (!d.isAfter(end)) {
    dates.push(d.format('YYYY-MM-DD'))
    d = d.add(1, 'day')
  }
  return dates
})

// Only workcenters that actually appear in this run's loadCells — a workcenter
// with zero aps_daily_plan rows has nothing to show and only pads the grid.
const activeWorkCenters = computed(() => {
  const byCode = new Map<string, string | null>()
  for (const c of store.loadCells) if (!byCode.has(c.wcCode)) byCode.set(c.wcCode, c.wcName)
  return [...byCode.entries()]
    .map(([code, name]) => ({ code, name }))
    .sort((a, b) => a.code.localeCompare(b.code))
})

const cellIndex = computed(() => {
  const idx = new Map<string, LoadCellStatus>()
  for (const c of store.loadCells) idx.set(`${c.wcCode}|${c.cellDate}`, c.status)
  return idx
})

const cellDetail = computed(() => {
  const idx = new Map<string, { loaded: number; capacity: number; status: LoadCellStatus }>()
  for (const c of store.loadCells)
    idx.set(`${c.wcCode}|${c.cellDate}`, {
      loaded: c.minutesLoaded,
      capacity: c.minutesCapacity,
      status: c.status,
    })
  return idx
})

function cellClass(wc: string, date: string): string {
  const status = cellIndex.value.get(`${wc}|${date}`)
  const selected =
    store.filter.cellSelection?.wcCode === wc && store.filter.cellSelection?.date === date
  const base = 'load-cell'
  const sel = selected ? ' selected' : ''
  if (!status || status === 'EMPTY') return `${base} empty${sel}`
  if (status === 'NORMAL') return `${base} normal${sel}`
  if (status === 'MATERIAL_SHORT') return `${base} material-short${sel}`
  if (status === 'OVERLOAD') return `${base} overload${sel}`
  return `${base} both${sel}`
}

function cellTitle(wc: string, date: string): string {
  const d = cellDetail.value.get(`${wc}|${date}`)
  if (!d) return `${wc} · ${date}`
  return `${wc} · ${date}\n${d.loaded} / ${d.capacity} min\n${d.status}`
}

function onCellClick(wc: string, date: string): void {
  const cur = store.filter.cellSelection
  if (cur && cur.wcCode === wc && cur.date === date) {
    store.filter.cellSelection = null
  } else {
    store.filter.cellSelection = { wcCode: wc, date }
  }
}

function shortDate(d: string): string {
  return dayjs(d).format('M/D')
}
</script>

<template>
  <div class="panel">
    <div class="panel-head">
      <div>
        <div class="panel-title">{{ t('loadMatrix.title') }}</div>
        <div class="panel-sub">{{ t('loadMatrix.subtitle') }}</div>
      </div>
      <div class="legend">
        <span><span class="dot normal" />{{ t('loadMatrix.legend.normal') }}</span>
        <span><span class="dot material-short" />{{ t('loadMatrix.legend.materialShort') }}</span>
        <span><span class="dot overload" />{{ t('loadMatrix.legend.overload') }}</span>
        <span><span class="dot both" />{{ t('loadMatrix.legend.both') }}</span>
        <span><span class="dot empty" />{{ t('loadMatrix.legend.empty') }}</span>
      </div>
    </div>
    <div class="matrix-scroll">
      <table class="matrix">
        <thead>
          <tr>
            <th class="wc-col">WC</th>
            <th v-for="d in dateRange" :key="d" class="date-col">{{ shortDate(d) }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="wc in activeWorkCenters" :key="wc.code">
            <td class="wc-name">{{ wc.code }} · {{ wc.name }}</td>
            <td v-for="d in dateRange" :key="d" class="cell-td">
              <div
                :class="cellClass(wc.code, d)"
                :title="cellTitle(wc.code, d)"
                @click="onCellClick(wc.code, d)"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.panel {
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 14px;
}
.panel-head {
  padding: 12px 14px;
  border-bottom: 1px solid var(--p-content-border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.panel-title {
  font-size: 14px;
  font-weight: 700;
}
.panel-sub {
  font-size: 11px;
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
  overflow-x: auto;
  padding: 10px 14px;
}
.matrix {
  border-collapse: collapse;
  min-width: 100%;
}
.matrix th,
.matrix td {
  padding: 3px;
  text-align: center;
}
.matrix .wc-col {
  min-width: 120px;
  text-align: left;
  padding-left: 4px;
  font-family: var(--aps-mono);
  color: var(--p-text-muted-color);
  font-size: 11px;
  font-weight: 600;
}
.matrix .date-col {
  font-family: var(--aps-mono);
  color: var(--p-text-muted-color);
  font-size: 10px;
  font-weight: 500;
  border-bottom: 1px solid var(--p-content-border-color);
  min-width: 26px;
}
.matrix .wc-name {
  text-align: left;
  padding-left: 4px;
  font-family: var(--aps-mono);
  font-size: 12px;
  font-weight: 700;
  border-right: 1px solid var(--p-content-border-color);
  color: var(--p-text-color);
  white-space: nowrap;
}
.cell-td {
  padding: 2px;
}
</style>
