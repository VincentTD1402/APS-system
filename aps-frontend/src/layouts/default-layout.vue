<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { setLocale, type Locale } from '@/i18n'
import Menubar from 'primevue/menubar'
import Button from 'primevue/button'
import SelectButton from 'primevue/selectbutton'
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'

const { t, locale } = useI18n()
const router = useRouter()

const langOptions = [
  { label: '한국어', value: 'ko' },
  { label: 'Tiếng Việt', value: 'vi' },
]
const currentLang = ref<Locale>(locale.value as Locale)

watch(currentLang, (v) => setLocale(v))

const menu = computed(() => [
  { label: t('nav.aps'), icon: 'pi pi-calendar', command: () => router.push('/aps') },
  {
    label: t('nav.masters'),
    icon: 'pi pi-database',
    items: [
      { label: t('nav.workCenters'), command: () => router.push('/masters/work-centers') },
      { label: t('nav.items'), command: () => router.push('/masters/items') },
      { label: t('nav.bom'), command: () => router.push('/masters/bom') },
      { label: t('nav.inventory'), command: () => router.push('/masters/inventory') },
    ],
  },
  { label: t('nav.mps'), icon: 'pi pi-list', command: () => router.push('/mps') },
])
</script>

<template>
  <div class="layout">
    <Menubar :model="menu" class="layout-menu">
      <template #start>
        <div class="brand">
          <i class="pi pi-bolt brand-icon" />
          <span class="brand-title">{{ t('app.title') }}</span>
        </div>
      </template>
      <template #end>
        <div class="lang-wrap">
          <SelectButton v-model="currentLang" :options="langOptions" option-label="label" option-value="value" size="small" />
        </div>
      </template>
    </Menubar>
    <main class="layout-content">
      <slot />
    </main>
  </div>
</template>

<style scoped>
.layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
.layout-menu {
  border-radius: 0;
  border-left: 0;
  border-right: 0;
  border-top: 0;
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-right: 24px;
}
.brand-icon {
  color: var(--p-primary-color);
  font-size: 18px;
}
.brand-title {
  font-weight: 700;
  font-size: 15px;
}
.lang-wrap {
  display: flex;
  align-items: center;
}
.layout-content {
  flex: 1;
  padding: 16px 20px;
}
</style>
