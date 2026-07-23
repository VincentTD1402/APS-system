<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useApsStore } from '@/stores/aps-store'
import { computed } from 'vue'
import dayjs from 'dayjs'
import type { LoadCellStatus } from '@/types/enums'
import type { WorkPlan } from '@/types/planning'

const { t, locale } = useI18n()
const store = useApsStore()

const dateRange = computed(() => {
  const dates: string[] = []
  let d = dayjs('2026-08-01')
  const end = dayjs('2026-08-31')
  while (!d.isAfter(end)) {
    dates.push(d.format('YYYY-MM-DD'))
    d = d.add(1, 'day')
  }
  return dates
})

const cellStatusIndex = computed(() => {
  const m = new Map<string, LoadCellStatus>()
  for (const c of store.loadCells) m.set(`${c.wcCode}|${c.cellDate}`, c.status)
  return m
})

const sortedPlans = computed(() =>
  [...store.workPlans].sort((a, b) => {
    if (a.wcCode !== b.wcCode) return a.wcCode.localeCompare(b.wcCode)
    return a.deliveryDate.localeCompare(b.deliveryDate)
  })
)

function qtyAt(plan: WorkPlan, date: string): number | null {
  const dp = plan.dailyPlans.find((d) => d.date === date)
  return dp ? dp.qty : null
}

function cellClass(wc: string, date: string, hasQty: boolean): string {
  if (!hasQty) return 'plan-cell empty'
  const status = cellStatusIndex.value.get(`${wc}|${date}`)
  if (!status || status === 'EMPTY' || status === 'NORMAL') return 'plan-cell normal'
  if (status === 'MATERIAL_SHORT') return 'plan-cell material-short'
  if (status === 'OVERLOAD') return 'plan-cell overload'
  return 'plan-cell both'
}

function shortDate(d: string): string {
  return dayjs(d).format('M/D')
}

function fmtQty(q: number): string {
  return Number.isInteger(q) ? q.toString() : q.toFixed(1)
}
</script>

<template>
  <div class="panel">
    <div class="panel-head">
      <div>
        <div class="panel-title">{{ t('planMatrix.title') }}</div>
        <div class="panel-sub">{{ t('planMatrix.subtitle') }}</div>
      </div>
    </div>
    <div class="scroll">
      <table class="plan-matrix">
        <thead>
          <tr>
            <th class="wc-col">{{ t('planMatrix.col.wc') }}</th>
            <th class="item-col">{{ t('planMatrix.col.item') }}</th>
            <th class="qty-col">{{ t('planMatrix.col.qty') }}</th>
            <th v-for="d in dateRange" :key="d" class="date-col">{{ shortDate(d) }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="plan in sortedPlans" :key="plan.id">
            <td class="wc-name mono">{{ plan.wcCode }}</td>
            <td class="item-name">
              {{ locale === 'ko' ? plan.itemNameKo : plan.itemNameVi }}
              <span class="tmp mono">· {{ plan.tmpPlanNo }}</span>
            </td>
            <td class="qty mono">{{ plan.planQty.toLocaleString() }}</td>
            <td
              v-for="d in dateRange"
              :key="d"
              :class="cellClass(plan.wcCode, d, qtyAt(plan, d) !== null)"
            >
              <span v-if="qtyAt(plan, d) !== null" class="mono">{{ fmtQty(qtyAt(plan, d)!) }}</span>
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
.scroll {
  overflow: auto;
  max-height: 280px; /* cap chiều cao — có nhiều WC/order thì scroll dọc */
  padding: 10px 14px;
}
.scroll thead th {
  position: sticky;
  top: 0;
  background: var(--p-content-background);
  z-index: 1;
}
.plan-matrix {
  border-collapse: collapse;
  min-width: 100%;
  font-size: 11px;
}
.plan-matrix th,
.plan-matrix td {
  padding: 3px 6px;
  text-align: center;
  border-right: 1px solid var(--p-content-border-color);
  border-bottom: 1px solid var(--p-content-border-color);
}
.plan-matrix thead th {
  background: var(--p-content-hover-background);
  color: var(--p-text-muted-color);
  font-family: var(--aps-mono);
  font-size: 10.5px;
  font-weight: 600;
  white-space: nowrap;
}
.wc-col,
.wc-name {
  min-width: 60px;
  text-align: left !important;
}
.item-col,
.item-name {
  min-width: 130px;
  text-align: left !important;
  white-space: nowrap;
}
.qty-col,
.qty {
  min-width: 60px;
  text-align: right !important;
  padding-right: 8px !important;
}
.date-col {
  min-width: 34px;
}
.wc-name {
  font-weight: 700;
  color: var(--p-text-color);
}
.item-name .tmp {
  color: var(--p-text-muted-color);
  font-size: 10px;
  margin-left: 4px;
}
.plan-cell {
  font-family: var(--aps-mono);
  font-weight: 600;
  min-width: 34px;
}
.plan-cell.empty {
  background: transparent;
  color: var(--p-text-muted-color);
}
.plan-cell.normal {
  background: rgba(47, 209, 136, 0.35);
  color: var(--p-text-color);
}
.plan-cell.material-short {
  background: rgba(79, 140, 255, 0.5);
  color: var(--p-text-color);
}
.plan-cell.overload {
  background: rgba(255, 159, 67, 0.55);
  color: #1a1204;
}
.plan-cell.both {
  background: rgba(255, 84, 104, 0.6);
  color: #fff;
}
</style>
