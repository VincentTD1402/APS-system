<script setup lang="ts">
import { useApsStore } from '@/stores/aps-store'

const store = useApsStore()
</script>

<template>
  <div class="filter-card">
    <div class="f-field">
      <span class="lbl">사업부</span>
      <div class="ctl select" style="width:120px">
        <select v-model="store.filter.businessUnit" aria-label="사업부">
          <option value="전체">전체</option>
          <option value="sel">선택</option>
        </select>
      </div>
    </div>
    <div class="f-field">
      <span class="lbl">계획구분</span>
      <div class="ctl select" style="width:90px">
        <select v-model="store.filter.planType" aria-label="계획구분">
          <option value="">선택</option>
          <option value="MPS">MPS</option>
          <option value="WO">WO</option>
        </select>
      </div>
    </div>
    <div class="f-field">
      <span class="lbl">요청일</span>
      <div class="ctl date" style="width:100px">
        <input type="date" v-model="store.filter.dateFrom" aria-label="요청일 시작" />
      </div>
      <span class="range-sep">~</span>
      <div class="ctl date" style="width:100px">
        <input type="date" v-model="store.filter.dateTo" class="ctl-date-end" aria-label="요청일 종료" />
      </div>
    </div>
    <div class="f-field">
      <span class="lbl">APS전표번호</span>
      <div class="ctl search" style="width:130px">
        <input type="search" v-model="store.filter.apsDocNo" placeholder="" aria-label="APS전표번호 검색" />
        <svg class="ic-search" width="13" height="14" viewBox="0 0 12.991 13.562" aria-hidden="true"><use href="#ic-search"/></svg>
      </div>
    </div>
    <div class="f-field">
      <span class="lbl">Rev.</span>
      <div class="ctl select" style="width:80px">
        <select v-model="store.filter.rev" aria-label="Rev.">
          <option value="">선택</option>
        </select>
      </div>
    </div>
    <div class="f-field">
      <span class="lbl">처리상태</span>
      <div class="ctl select" style="width:90px">
        <select v-model="store.filter.status" aria-label="처리상태">
          <option value="">선택</option>
        </select>
      </div>
    </div>
    <div class="f-field">
      <span class="lbl">담당자</span>
      <div class="ctl search" style="width:130px">
        <input type="search" v-model="store.filter.owner" placeholder="" aria-label="담당자 검색" />
        <svg class="ic-search" width="13" height="14" viewBox="0 0 12.991 13.562" aria-hidden="true"><use href="#ic-search"/></svg>
      </div>
    </div>
    <div class="f-field">
      <span class="lbl">부서</span>
      <div class="ctl search" style="width:130px">
        <input type="search" v-model="store.filter.dept" placeholder="" aria-label="부서 검색" />
        <svg class="ic-search" width="13" height="14" viewBox="0 0 12.991 13.562" aria-hidden="true"><use href="#ic-search"/></svg>
      </div>
    </div>
  </div>
</template>
