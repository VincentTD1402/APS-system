<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useApsStore } from '@/stores/aps-store'

const store = useApsStore()
const { t } = useI18n()
</script>

<template>
  <div class="filter-card">
    <div class="f-field">
      <span class="lbl">{{ t('filterBar.businessUnit') }}</span>
      <div class="ctl select" style="width:120px">
        <select v-model="store.filter.businessUnit" :aria-label="t('filterBar.businessUnit')">
          <option value="전체">{{ t('common.all') }}</option>
          <option value="sel">{{ t('common.select') }}</option>
        </select>
      </div>
    </div>
    <div class="f-field">
      <span class="lbl">{{ t('filterBar.planType') }}</span>
      <div class="ctl select" style="width:90px">
        <select v-model="store.filter.planType" :aria-label="t('filterBar.planType')">
          <option value="">{{ t('common.select') }}</option>
          <option value="MPS">MPS</option>
          <option value="WO">WO</option>
        </select>
      </div>
    </div>
    <div class="f-field">
      <span class="lbl">{{ t('filterBar.requestDate') }}</span>
      <div class="ctl date" style="width:100px">
        <input type="date" v-model="store.filter.dateFrom" :aria-label="`${t('filterBar.requestDate')} ${t('detail.info.start')}`" />
      </div>
      <span class="range-sep">~</span>
      <div class="ctl date" style="width:100px">
        <input type="date" v-model="store.filter.dateTo" class="ctl-date-end" :aria-label="`${t('filterBar.requestDate')} ${t('detail.info.end')}`" />
      </div>
    </div>
    <div class="f-field">
      <span class="lbl">{{ t('filterBar.apsDocNo') }}</span>
      <div class="ctl search" style="width:130px">
        <input type="search" v-model="store.filter.apsDocNo" placeholder="" :aria-label="`${t('filterBar.apsDocNo')} ${t('common.search')}`" />
        <svg class="ic-search" width="13" height="14" viewBox="0 0 12.991 13.562" aria-hidden="true"><use href="#ic-search"/></svg>
      </div>
    </div>
    <div class="f-field">
      <span class="lbl">{{ t('filterBar.rev') }}</span>
      <div class="ctl select" style="width:80px">
        <select v-model="store.filter.rev" :aria-label="t('filterBar.rev')">
          <option value="">{{ t('common.select') }}</option>
        </select>
      </div>
    </div>
    <div class="f-field">
      <span class="lbl">{{ t('filterBar.status') }}</span>
      <div class="ctl select" style="width:90px">
        <select v-model="store.filter.status" :aria-label="t('filterBar.status')">
          <option value="">{{ t('common.select') }}</option>
        </select>
      </div>
    </div>
    <div class="f-field">
      <span class="lbl">{{ t('filterBar.owner') }}</span>
      <div class="ctl search" style="width:130px">
        <input type="search" v-model="store.filter.owner" placeholder="" :aria-label="`${t('filterBar.owner')} ${t('common.search')}`" />
        <svg class="ic-search" width="13" height="14" viewBox="0 0 12.991 13.562" aria-hidden="true"><use href="#ic-search"/></svg>
      </div>
    </div>
    <div class="f-field">
      <span class="lbl">{{ t('filterBar.dept') }}</span>
      <div class="ctl search" style="width:130px">
        <input type="search" v-model="store.filter.dept" placeholder="" :aria-label="`${t('filterBar.dept')} ${t('common.search')}`" />
        <svg class="ic-search" width="13" height="14" viewBox="0 0 12.991 13.562" aria-hidden="true"><use href="#ic-search"/></svg>
      </div>
    </div>
  </div>
</template>
