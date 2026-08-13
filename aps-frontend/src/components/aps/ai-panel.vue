<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useApsStore } from '@/stores/aps-store'

const store = useApsStore()
const { t } = useI18n()

const facts = computed(() => store.aiSummary?.facts ?? null)
const narrative = computed(() => store.aiSummary?.narrative ?? null)

/** 영향받는 작업장 — every overloaded workcenter, not just the worst one. */
const workcenterList = computed(() =>
  (facts.value?.workcenters ?? []).map((w) => w.workcenterNo ?? '-').join(', ')
)

// The prompt asks the model to open root_cause with "[SEVERITY] ", but a model is
// not a guarantee: strip the tag if present and render the badge from
// facts.severity, which is computed server-side and always right.
const ROOT_CAUSE_TAG = /^\[[A-Z]+\]\s*/

const rootCauseText = computed(() =>
  (narrative.value?.rootCause ?? '').replace(ROOT_CAUSE_TAG, '')
)

const severityClass = computed(() => {
  switch (facts.value?.severity) {
    case 'CRITICAL': return 'sev-critical'
    case 'WARNING': return 'sev-warning'
    default: return 'sev-low'
  }
})

const numberFormat = new Intl.NumberFormat('en-US')
const fmt = (n: number): string => numberFormat.format(n)

// A stale reading is worth showing — with a marker — rather than blanking the
// panel because one request failed.
const showStale = computed(() => Boolean(store.aiError) && Boolean(store.aiSummary))
</script>

<template>
  <div class="ai-panel area-ai">
    <div class="ai-header">
      <svg class="ic-bulb" aria-hidden="true"><use href="#ic-bulb"/></svg>
      {{ t('aiPanel.header') }}
    </div>
    <div class="ai-body">
      <!-- Nothing loaded yet: this panel is driven by RUN APS. -->
      <div v-if="!store.hasData" class="ai-content ai-placeholder">
        {{ t('aiPanel.placeholder') }}
      </div>

      <div v-else-if="store.aiLoading && !store.aiSummary" class="ai-content" aria-busy="true">
        <div class="sk sk-title"></div>
        <div class="sk sk-line"></div>
        <div class="sk sk-line"></div>
        <div class="sk sk-line short"></div>
        <div class="sk sk-title"></div>
        <div class="sk sk-line"></div>
        <div class="sk sk-line short"></div>
      </div>

      <div v-else-if="store.aiError && !store.aiSummary" class="ai-content ai-error">
        <p>{{ t('aiPanel.errorMsg') }}</p>
        <button type="button" class="ai-retry" @click="store.loadAiSummary()">{{ t('aiPanel.retry') }}</button>
      </div>

      <div v-else-if="facts && narrative" class="ai-content">
        <div class="ai-doc-title">{{ t('aiPanel.docTitle') }}</div>
        <p v-if="showStale" class="ai-stale">{{ t('aiPanel.stale') }}</p>

        <p class="ai-num"><b>{{ t('aiPanel.section1') }}</b></p>
        <p>
          <span class="ai-sev" :class="severityClass">[{{ facts.severity }}]</span>
          {{ rootCauseText }}
        </p>

        <p class="ai-num"><b>{{ t('aiPanel.section2') }}</b></p>
        <!-- Figures come from `facts`; the prose below only describes them. -->
        <p v-if="facts.workcenters.length">{{ t('aiPanel.affectedWc', { list: workcenterList }) }}</p>
        <p>{{ t('aiPanel.affectedOrder', { count: facts.affected.count }) }}</p>
        <p>{{ t('aiPanel.severityLine', { severity: facts.severity, urgency: facts.urgency }) }}</p>
        <p v-for="s in facts.shortages" :key="`${s.parentItemNo}-${s.itemNo}`">
          {{ t('aiPanel.materialShort', { name: s.itemName ?? s.itemNo, onHand: fmt(s.availableQty), shortage: fmt(s.shortageQty) }) }}
        </p>
        <p>{{ narrative.impactSummary }}</p>

        <p class="ai-num"><b>{{ t('aiPanel.section3') }}</b></p>
        <p v-for="r in narrative.recommendations" :key="r.priority">
          {{ t('aiPanel.priorityLine', { priority: r.priority, text: r.text }) }}
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ai-placeholder,
.ai-error {
  color: #8a8a94;
}
.ai-stale {
  color: #B26A00;
  font-size: 12px;
}
.ai-sev {
  font-weight: 700;
}
.sev-critical { color: #DC3044; }
.sev-warning  { color: #B26A00; }
.sev-low      { color: #2E7D32; }

.ai-retry {
  margin-top: 4px;
  padding: 4px 10px;
  font-size: 12px;
  font-family: inherit;
  color: #222222;
  background: #ffffff;
  border: 1px solid #dedede;
  border-radius: 4px;
  cursor: pointer;
}
.ai-retry:hover {
  background: #f5f5f7;
}

/* Skeleton — sized close to the real block so the panel does not jump. */
.sk {
  background: linear-gradient(90deg, #f0f0f3 25%, #e6e6ea 37%, #f0f0f3 63%);
  background-size: 400% 100%;
  border-radius: 3px;
  animation: sk-shimmer 1.4s ease-in-out infinite;
}
.sk-title {
  height: 13px;
  width: 45%;
  margin: 10px 0 8px;
}
.sk-line {
  height: 11px;
  margin-bottom: 7px;
}
.sk-line.short {
  width: 70%;
}
@keyframes sk-shimmer {
  from { background-position: 100% 50%; }
  to   { background-position: 0 50%; }
}
@media (prefers-reduced-motion: reduce) {
  .sk { animation: none; }
}
</style>
