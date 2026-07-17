import { createI18n } from 'vue-i18n'
import ko from './ko.json'
import vi from './vi.json'

export const SUPPORTED_LOCALES = ['ko', 'vi'] as const
export type Locale = (typeof SUPPORTED_LOCALES)[number]

const stored = (localStorage.getItem('aps.locale') as Locale) || 'vi'

export const i18n = createI18n({
  legacy: false,
  locale: stored,
  fallbackLocale: 'ko',
  messages: { ko, vi },
})

export function setLocale(locale: Locale): void {
  i18n.global.locale.value = locale
  localStorage.setItem('aps.locale', locale)
  document.documentElement.setAttribute('lang', locale)
}
